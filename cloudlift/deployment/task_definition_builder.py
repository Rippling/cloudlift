from troposphere.ecs import (AwsvpcConfiguration, ContainerDefinition,
                             DeploymentConfiguration, Environment, Secret,
                             LoadBalancer, LogConfiguration,
                             NetworkConfiguration, PlacementStrategy,
                             PortMapping, Service, TaskDefinition, PlacementConstraint, SystemControl,
                             HealthCheck)
from troposphere import Output, Ref, Template


class TaskDefinitionBuilder:
    def __init__(self, environment, service_name, configuration, region):
        self.environment = environment
        self.service_name = service_name
        self.configuration = configuration
        self.region = region

    def build_dict(self,
                   container_configurations,
                   ecr_image_uri,
                   ):
        t = Template()
        t.add_resource(self.build_template_resource(
            container_configurations,
            ecr_image_uri=ecr_image_uri,

        ))
        task_definition = t.to_dict()["Resources"][self._resource_name(self.service_name)]["Properties"]
        return camelize_keys(task_definition)

    def build_template_resource(
            self,
            container_configurations,
            ecr_image_uri
    ):
        environment = self.environment
        service_name = self.service_name
        config = self.configuration
        task_family_name = f'{environment}{service_name}Family'[:255]
        td_kwargs = dict()

        if 'placement_constraints' in config:
            td_kwargs['PlacementConstraints'] = [
                PlacementConstraint(Type=constraint['type'],
                                    Expression=constraint['expression']) for constraint in
                config['placement_constraints']
            ]

        if 'task_role_arn' in config:
            td_kwargs['TaskRoleArn'] = config.get('task_role_arn')

        if 'task_execution_role_arn' in config:
            td_kwargs['ExecutionRoleArn'] = config.get('task_execution_role_arn')

        if ('udp_interface' in config) or ('tcp_interface' in config):
            td_kwargs['NetworkMode'] = 'awsvpc'

        log_config = self._gen_log_config()
        env_config = container_configurations[container_name(service_name)].get('environment', {})
        secrets_config = container_configurations[container_name(service_name)].get('secrets', {})

        cd_kwargs = {
            "Environment": [Environment(Name=name, Value=env_config[name]) for name in env_config],
            "Secrets": [Secret(Name=name, ValueFrom=secrets_config[name]) for name in secrets_config],
            "Name": container_name(service_name),
            "Image": ecr_image_uri,
            "Essential": 'true',
            "LogConfiguration": log_config,
            "MemoryReservation": int(config['memory_reservation']),
            "Cpu": 0
        }

        if config['command'] is not None:
            cd_kwargs['Command'] = [config['command']]

        if 'stop_timeout' in config:
            cd_kwargs['StopTimeout'] = int(config['stop_timeout'])

        if 'system_controls' in config:
            cd_kwargs['SystemControls'] = [SystemControl(Namespace=system_control['namespace'],
                                                         Value=system_control['value']) for
                                           system_control in config['system_controls']]

        if 'http_interface' in config:
            cd_kwargs['PortMappings'] = [
                PortMapping(
                    ContainerPort=int(
                        config['http_interface']['container_port']
                    )
                )
            ]
        elif 'udp_interface' in config:
            cd_kwargs['PortMappings'] = [
                PortMapping(ContainerPort=int(config['udp_interface']['container_port']),
                            HostPort=int(config['udp_interface']['container_port']), Protocol='udp'),
                PortMapping(ContainerPort=int(config['udp_interface']['health_check_port']),
                            HostPort=int(config['udp_interface']['health_check_port']), Protocol='tcp')
            ]
        elif 'tcp_interface' in config:
            cd_kwargs['PortMappings'] = [
                PortMapping(ContainerPort=int(config['tcp_interface']['container_port']), Protocol='tcp')
            ]

        if 'container_health_check' in config:
            configured_health_check = config['container_health_check']
            ecs_health_check = {'Command': ['CMD-SHELL', configured_health_check['command']]}
            if 'start_period' in configured_health_check:
                ecs_health_check['StartPeriod'] = int(configured_health_check['start_period'])
            if 'retries' in configured_health_check:
                ecs_health_check['Retries'] = int(configured_health_check['retries'])
            if 'interval' in configured_health_check:
                ecs_health_check['Interval'] = int(configured_health_check['interval'])
            if 'timeout' in configured_health_check:
                ecs_health_check['Timeout'] = int(configured_health_check['timeout'])
            cd_kwargs['HealthCheck'] = HealthCheck(
                **ecs_health_check
            )

        if 'sidecars' in config:
            links = []
            for sidecar in config['sidecars']:
                sidecar_name = sidecar.get('name')
                links.append(
                    "{}:{}".format(container_name(sidecar_name), sidecar_name)
                )
            cd_kwargs['Links'] = links

        if 'container_labels' in config:
            cd_kwargs['DockerLabels'] = config.get('container_labels')

        cd = ContainerDefinition(**cd_kwargs)
        container_definitions = [cd]
        if 'sidecars' in config:
            for sidecar in config['sidecars']:
                container_definitions.append(
                    self._gen_container_definitions_for_sidecar(sidecar,
                                                                log_config,
                                                                container_configurations.get(
                                                                    container_name(sidecar.get('name')),
                                                                    {})),
                )
        return TaskDefinition(
            self._resource_name(service_name),
            Family=task_family_name,
            ContainerDefinitions=container_definitions,
            **td_kwargs
        )

    def _resource_name(self, service_name):
        return service_name + "TaskDefinition"

    def _gen_log_config(self):
        env_log_group = '-'.join([self.environment, 'logs'])
        return LogConfiguration(
            LogDriver="awslogs",
            Options={
                'awslogs-stream-prefix': self.service_name,
                'awslogs-group': self.configuration.get('log_group', env_log_group),
                'awslogs-region': self.region
            }
        )

    def _gen_container_definitions_for_sidecar(self, sidecar, log_config, env_config):
        cd = dict()

        if 'command' in sidecar:
            cd['Command'] = sidecar['command']

        return ContainerDefinition(
            Name=container_name(sidecar.get('name')),
            Environment=[Environment(Name=k, Value=v) for (k, v) in env_config],
            MemoryReservation=int(sidecar.get('memory_reservation')),
            Image=sidecar.get('image'),
            LogConfiguration=log_config,
            Essential=False,
            **cd
        )


def camelize_keys(data):
    if not isinstance(data, dict):
        return data

    result = dict()
    for k, v in data.items():
        key = _camel_case(k)
        if isinstance(v, dict):
            result[key] = camelize_keys(v)
        elif isinstance(v, list):
            elements = list()
            for each in v:
                elements.append(camelize_keys(each))
            result[key] = elements
        else:
            result[key] = v
    return result


def _camel_case(value):
    return value[:1].lower() + value[1:]


def container_name(service_name):
    return service_name + "Container"


def strip_container_name(name):
    return name.replace("Container", "")
