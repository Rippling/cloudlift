from unittest import TestCase
from cloudlift.deployment.task_definition_builder import TaskDefinitionBuilder


class TaskDefinitionBuilderTest(TestCase):
    def test_build_dict_for_http_api(self):
        configuration = {
            'command': './start_script.sh',
            'http_interface': {'container_port': 9090},
            'memory_reservation': 100,
            'stop_timeout': 70,
            'system_controls': [{"namespace": "net.core.somaxconn", "value": "1024"}],
            'task_execution_role_arn': 'arn1',
            'task_role_arn': 'arn2',
            'placement_constraints': [{'type': 'memberOf', 'expression': 'expr'}]
        }
        builder = TaskDefinitionBuilder(
            environment="test",
            service_name="dummy",
            configuration=configuration,
            region='region1',
        )

        expected = {
            'containerDefinitions': [{
                'command': ['./start_script.sh'],
                'cpu': 0,
                'environment': [{'name': 'PORT', 'value': '80'}],
                'essential': 'true',
                'image': 'nginx:default',
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': 'test-logs',
                        'awslogs-region': 'region1',
                        'awslogs-stream-prefix': 'dummy',
                    },
                },
                'memoryReservation': 100,
                'name': 'dummyContainer',
                'portMappings': [{'containerPort': 9090}],
                'secrets': [{'name': 'CLOUDLIFT_INJECTED_SECRETS', 'valueFrom': 'arn_injected_secrets'}],
                'stopTimeout': 70,
                'systemControls': [{'namespace': 'net.core.somaxconn', 'value': '1024'}],
            }],
            'executionRoleArn': 'arn1',
            'family': 'testdummyFamily',
            'taskRoleArn': 'arn2',
            'placementConstraints': [{'type': 'memberOf', 'expression': 'expr'}]
        }

        actual = builder.build_dict(
            container_configurations={
                'dummyContainer': {
                    "secrets": {"CLOUDLIFT_INJECTED_SECRETS": 'arn_injected_secrets'},
                    "environment": {"PORT": "80"}
                },
            },
            ecr_image_uri="nginx:default"
        )

        self.assertEqual(expected, actual)
