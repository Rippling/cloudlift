'''
This module abstracts implementation of storing, editing and
retrieving service configuration.
'''

import json

import dictdiffer
from botocore.exceptions import ClientError
from click import confirm, edit
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from stringcase import pascalcase, spinalcase
from os import getcwd
from os.path import basename

from cloudlift.config import DecimalEncoder, DynamodbConfig
# import config.mfa as mfa
from cloudlift.config import print_json_changes
from cloudlift.config.logging import log_bold, log_warning
from cloudlift.exceptions import UnrecoverableException
from cloudlift.version import VERSION

SERVICE_CONFIGURATION_TABLE = 'service_configurations'
DEFAULT_TARGET_GROUP_DEREGISTRATION_DELAY = 30
DEFAULT_LOAD_BALANCING_ALGORITHM = u'least_outstanding_requests'
DEFAULT_HEALTH_CHECK_HEALTHY_THRESHOLD_COUNT = 2
DEFAULT_HEALTH_CHECK_UNHEALTHY_THRESHOLD_COUNT = 3
DEFAULT_HEALTH_CHECK_INTERVAL_SECONDS = 30
DEFAULT_HEALTH_CHECK_TIMEOUT_SECONDS = 10


class ServiceConfiguration(DynamodbConfig):
    '''
        Handles configuration in DynamoDB for services
    '''

    def __init__(self, service_name, environment):
        self.service_name = service_name
        self.environment = environment
        self.new_service = False
        # TODO: Use the below two lines when all parameter store actions
        # require MFA
        #
        # mfa_region = get_region_for_environment(environment)
        # mfa_session = mfa.get_mfa_session(mfa_region)
        # ssm_client = mfa_session.client('ssm')
        super(ServiceConfiguration, self).__init__(SERVICE_CONFIGURATION_TABLE, [
            ('service_name', self.service_name), ('environment', self.environment)])

    def edit_config(self):
        '''
            Open editor to update configuration
        '''

        try:
            current_configuration = self.get_config()

            updated_configuration = edit(
                text=json.dumps(
                    current_configuration,
                    indent=4,
                    sort_keys=True,
                    cls=DecimalEncoder
                ),
                extension=".json"
            )

            if updated_configuration is None:
                if self.new_service:
                    self.set_config(current_configuration)
                    log_warning("Using default configuration.")
                else:
                    log_warning("No changes made.")
            else:
                updated_configuration = json.loads(updated_configuration)
                differences = list(dictdiffer.diff(
                    current_configuration,
                    updated_configuration
                ))
                if not differences:
                    log_warning("No changes made.")
                else:
                    print_json_changes(differences)
                    if confirm('Do you want update the config?'):
                        self.set_config(updated_configuration)
                    else:
                        log_warning("Changes aborted.")
        except ClientError:
            raise UnrecoverableException("Unable to fetch service configuration from DynamoDB.")

    def get_config(self, strip_cloudlift_version=True):
        '''
            Get configuration from DynamoDB
        '''
        existing_configuration = self.get_config_in_db()
        if not existing_configuration:
            existing_configuration = self._default_service_configuration()
            self.new_service = True
        if strip_cloudlift_version:
            existing_configuration.pop("cloudlift_version", None)
        return existing_configuration

    def set_config(self, config):
        '''
            Set configuration in DynamoDB
        '''
        config['cloudlift_version'] = VERSION
        self.set_config_in_db(config)

    def update_cloudlift_version(self):
        '''
            Updates cloudlift version in service configuration
        '''
        config = self.get_config()
        self.set_config(config)

    def validate(self):
        log_bold("Running post-save validation:")
        self._validate_changes(self.get_config(strip_cloudlift_version=False))

    def _validate_changes(self, configuration):
        service_schema = {
            "title": "service",
            "type": "object",
            "properties": {
                "http_interface": {
                    "type": "object",
                    "properties": {
                        "internal": {
                            "type": "boolean"
                        },
                        "alb": {
                            "type": "object",
                            "properties": {
                                "create_new": {
                                    "type": "boolean",
                                },
                                "listener_arn": {
                                    "type": "string"
                                },
                                "host": {
                                    "type": "string"
                                },
                                "path": {
                                    "type": "string"
                                },
                                "priority": {
                                    "type": "number"
                                }
                            },
                            "required": [
                                "create_new"
                            ]
                        },
                        "restrict_access_to": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "container_port": {
                            "type": "number"
                        },
                        "health_check_path": {
                            "type": "string",
                            "pattern": "^\/.*$"
                        },
                        "health_check_healthy_threshold_count": {
                            "type": "number",
                            "minimum": 2,
                            "maximum": 10
                        },
                        "health_check_unhealthy_threshold_count": {
                            "type": "number",
                            "minimum": 2,
                            "maxium": 10
                        },
                        "health_check_interval_seconds": {
                            "type": "number",
                            "minimum": 5,
                            "maximum": 300
                        },
                        "health_check_timeout_seconds": {
                            "type": "number",
                            "minimum": 2,
                            "maximum": 120
                        },
                    },
                    "load_balancing_algorithm": {
                        "type": "string",
                        "enum": ["round_robin", "least_outstanding_requests"]
                    },
                    "deregistration_delay": {
                        "type": "number"
                    },
                    "required": [
                        "internal",
                        "restrict_access_to",
                        "container_port"
                    ]
                },
                "memory_reservation": {
                    "type": "number",
                    "minimum": 10,
                    "maximum": 30000
                },
                "deployment": {
                    "type": "object",
                    "properties": {
                        "maximum_percent": {
                            "type": "number",
                            "minimum": 100,
                            "maximum": 200
                        },
                    },
                    "required": ["maximum_percent"]
                },
                "fargate": {
                    "type": "object",
                    "properties": {
                        "cpu": {
                            "type": "number",
                            "minimum": 256,
                            "maximum": 4096
                        },
                        "memory": {
                            "type": "number",
                            "minimum": 512,
                            "maximum": 30720
                        }
                    }
                },
                "command": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "null"}
                    ]
                },
                "stop_timeout": {
                    "type": "number"
                },
                "container_health_check": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string"
                        },
                        "start_period": {
                            "type": "number"
                        },
                        "retries": {
                            "type": "number",
                            "minimum": 1,
                            "maximum": 10
                        },
                        "interval": {
                            "type": "number",
                            "minimum": 5,
                            "maximum": 300
                        },
                        "timeout": {
                            "type": "number",
                            "minimum": 2,
                            "maximum": 60
                        },
                    },
                    "required": ["command"]
                },
                "placement_constraints": {
                    "type": "array",
                    "items": {
                        "required": ["type"],
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["memberOf", "distinctInstance"],
                            },
                            "expression": {
                                "type": "string"
                            }
                        }
                    },
                },
                "sidecars": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string"
                            },
                            "image": {
                                "type": "string"
                            },
                            "command": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "memory_reservation": {
                                "type": "number"
                            }
                        },
                        "required": ["name", "image", "memory_reservation"]
                    }
                },
                "system_controls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string"
                            },
                            "value": {
                                "type": "string"
                            }
                        }
                    },
                },
                "log_group": {
                    "type": "string",
                },
                "secrets_name": {
                    "type": "string",
                },
                "task_role_attached_managed_policy_arns": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "autoscaling": {
                    "type": "object",
                    "properties": {
                        "max_capacity": {
                            "type": "number"
                        },
                        "min_capacity": {
                            "type": "number"
                        },
                        "request_count_per_target": {
                            "type": "object",
                            "properties": {
                                "alb_arn": {
                                    "type": "string"
                                },
                                "target_value": {
                                    "type": "number"
                                },
                                "scale_in_cool_down_seconds": {
                                    "type": "number"
                                },
                                "scale_out_cool_down_seconds": {
                                    "type": "number"
                                }
                            },
                            "required": ['target_value', 'scale_in_cool_down_seconds', 'scale_out_cool_down_seconds']
                        },
                    },
                    "required": ['max_capacity', 'min_capacity', 'request_count_per_target']
                },
                "container_labels": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string"}
                    },
                    "additionalProperties": False
                },
            },
            "required": ["memory_reservation", "command", "secrets_name"]
        }
        schema = {
            # "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "configuration",
            "type": "object",
            "properties": {
                "notifications_arn": {
                    "type": "string"
                },
                "services": {
                    "type": "object",
                    "patternProperties": {
                        "^[a-zA-Z]+$": service_schema
                    }
                },
                "ecr_repo": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "assume_role_arn": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["name"]
                },
                "cloudlift_version": {
                    "type": "string"
                }
            },
            "required": ["cloudlift_version", "services", "ecr_repo"]
        }
        try:
            validate(configuration, schema)
        except ValidationError as validation_error:
            errors = [str(i) for i in validation_error.relative_path]
            raise UnrecoverableException(validation_error.message + " in " +
                                         str(".".join(list(errors))))
        log_bold("Schema valid!")

    def _default_service_configuration(self):
        cwd = basename(getcwd())
        return {
            u'ecr_repo': {
                u'name': spinalcase("{}-repo".format(cwd)),
            },
            u'services': {
                pascalcase(self.service_name): {
                    u'http_interface': {
                        u'internal': False,
                        u'alb': {
                            u'create_new': True,
                        },
                        u'restrict_access_to': [u'0.0.0.0/0'],
                        u'container_port': 80,
                        u'health_check_path': u'/elb-check',
                        u'load_balancing_algorithm': DEFAULT_LOAD_BALANCING_ALGORITHM,
                        u'deregistartion_delay': DEFAULT_TARGET_GROUP_DEREGISTRATION_DELAY
                    },
                    u'secrets_name': spinalcase("{}-{}".format(self.service_name, self.environment)),
                    u'system_controls': [],
                    u'memory_reservation': 1000,
                    u'command': None
                }
            }
        }
