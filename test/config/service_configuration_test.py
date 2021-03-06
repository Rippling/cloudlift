from unittest import TestCase
from unittest.mock import patch

import boto3
from moto import mock_dynamodb2

from cloudlift.config import ServiceConfiguration
from cloudlift.exceptions import UnrecoverableException
from cloudlift.version import VERSION
from dictdiffer import diff, are_different


class TestServiceConfiguration(object):
    class DictDifferenceException(Exception):
        pass

    def evaluate_difference(self, dict_a, dict_b):
        if are_different(dict_a, dict_b, 0):
            print("Expected response different than actual:")
            for d in list(diff(dict_a, dict_b)):
                print(d)
            raise self.DictDifferenceException("DictDifference")

    def setup_existing_params(self):
        client = boto3.resource('dynamodb')
        client.create_table(
            TableName='service_configurations',
            AttributeDefinitions=[
                {
                    'AttributeName': 'service_name',
                    'AttributeType': 'S',
                },
                {
                    'AttributeName': 'environment',
                    'AttributeType': 'S',
                }
            ],
            KeySchema=[
                {
                    'AttributeName': 'service_name',
                    'KeyType': 'HASH',
                },
                {
                    'AttributeName': 'environment',
                    'KeyType': 'RANGE',
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        )
        table = client.Table('service_configurations')
        table.update_item(
            TableName='service_configurations',
            Key={
                'service_name': 'test-service',
                'environment': 'dummy-staging'
            },
            UpdateExpression='SET configuration = :configuration',
            ExpressionAttributeValues={
                ':configuration': {
                    "cloudlift_version": VERSION,
                    'ecr_repo': {'name': 'test-service-repo'},
                    "services": {
                        "TestService": {
                            "memory_reservation": 1000,
                            "secrets_name": "secret-config",
                            "command": None,
                            "http_interface": {
                                "internal": True,
                                "container_port": 80,
                                "restrict_access_to": ["0.0.0.0/0"]
                            }
                        }
                    }
                }
            },
            ReturnValues="UPDATED_NEW"
        )

    def setup_params_for_listener_selection(self):
        client = boto3.resource('dynamodb')
        client.create_table(
            TableName='service_configurations',
            AttributeDefinitions=[
                {
                    'AttributeName': 'service_name',
                    'AttributeType': 'S',
                },
                {
                    'AttributeName': 'environment',
                    'AttributeType': 'S',
                }
            ],
            KeySchema=[
                {
                    'AttributeName': 'service_name',
                    'KeyType': 'HASH',
                },
                {
                    'AttributeName': 'environment',
                    'KeyType': 'RANGE',
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        )
        table = client.Table('service_configurations')
        table.update_item(
            TableName='service_configurations',
            Key={
                'service_name': 'test-service',
                'environment': 'dummy-staging'
            },
            UpdateExpression='SET configuration = :configuration',
            ExpressionAttributeValues={
                ':configuration': {
                    "cloudlift_version": VERSION,
                    'ecr_repo': {'name': 'test-service-repo'},
                    "services": {
                        "TestService": {
                            "memory_reservation": 1000,
                            "command": None,
                            "http_interface": {
                                "alb": {
                                    "create_new": False,
                                    "listener_arn": 'random-listener-arn',
                                    "host": "host-address.com",
                                    "target_5xx_error_threshold": 5
                                },
                                "internal": True,
                                "container_port": 80,
                                "restrict_access_to": ["0.0.0.0/0"]
                            }
                        }
                    }
                }
            },
            ReturnValues="UPDATED_NEW"
        )

    @mock_dynamodb2
    def test_initialization(self):
        store_object = ServiceConfiguration('test-service', 'dummy-staging')
        assert store_object.environment == 'dummy-staging'
        assert store_object.service_name == 'test-service'
        assert store_object.table is not None

    @mock_dynamodb2
    def test_get_config(self):
        self.setup_existing_params()

        store_object = ServiceConfiguration('test-service', 'dummy-staging')
        response = store_object.get_config()
        assert response == {
            'ecr_repo': {'name': 'test-service-repo'},
            "services": {
                "TestService": {
                    "memory_reservation": 1000,
                    'secrets_name': 'secret-config',
                    "command": None,
                    "http_interface": {
                        "internal": True,
                        "container_port": 80,
                        "restrict_access_to": [u'0.0.0.0/0'],
                    }
                }
            }
        }

    @mock_dynamodb2
    def test_set_config(self):
        self.setup_existing_params()

        store_object = ServiceConfiguration('test-service', 'dummy-staging')
        get_response = store_object.get_config()

        get_response["services"]["TestService"]["http_interface"]["restrict_access_to"] = [u"123.123.123.123/32"]
        store_object.set_config(get_response)
        update_response = store_object.get_config()

        assert update_response == {
            'ecr_repo': {'name': 'test-service-repo'},
            "services": {
                "TestService": {
                    "memory_reservation": 1000,
                    'secrets_name': 'secret-config',
                    "command": None,
                    "http_interface": {
                        "internal": True,
                        "container_port": 80,
                        "restrict_access_to": [u"123.123.123.123/32"],
                    }
                }
            }
        }

    @mock_dynamodb2
    @patch("cloudlift.config.service_configuration.ServiceConfiguration._get_listener_rule_priority_for_service")
    def test_set_config_with_random_listner_priority(self, mock_get_listener_rule_priority):
        self.setup_params_for_listener_selection()
        mock_get_listener_rule_priority.return_value = 23
        store_object = ServiceConfiguration('test-service', 'dummy-staging')
        get_response = store_object.get_config()

        get_response["services"]["TestService"]["http_interface"]["restrict_access_to"] = [u"123.123.123.123/32"]
        store_object.set_config(get_response)
        update_response = store_object.get_config()

        expected_response = {
            'ecr_repo': {
                'name': 'test-service-repo'
            },
            'services': {
                'TestService': {
                    'memory_reservation': 1000,
                    'command': None,
                    'http_interface': {
                        'alb': {'create_new': False,
                                'listener_arn': 'random-listener-arn',
                                'host': 'host-address.com',
                                'priority': 23,
                                'target_5xx_error_threshold': 5
                                },
                        'internal': True,
                        'container_port': 80,
                        'restrict_access_to': ['123.123.123.123/32']}}
            }
        }

    @mock_dynamodb2
    def test_set_config_stop_timeout(self):
        self.setup_existing_params()

        store_object = ServiceConfiguration('test-service', 'dummy-staging')
        get_response = store_object.get_config()

        get_response["services"]["TestService"]["stop_timeout"] = 120
        store_object.set_config(get_response)
        update_response = store_object.get_config()

        assert update_response == {
            "ecr_repo": {"name": "test-service-repo"},
            "services": {
                "TestService": {
                    "memory_reservation": 1000,
                    'secrets_name': 'secret-config',
                    "command": None,
                    "http_interface": {
                        "internal": True,
                        "container_port": 80,
                        "restrict_access_to": [u'0.0.0.0/0'],
                    },
                    "stop_timeout": 120
                }
            }
        }


class TestServiceConfigurationValidation(TestCase):
    @mock_dynamodb2
    @patch("cloudlift.config.service_configuration.getcwd")
    def test_default_service_configuration_ecr_repo(self, getcwd):
        getcwd.return_value = "/path/to/dummy"

        service = ServiceConfiguration('test-service', 'test')
        conf = service._default_service_configuration()

        self.assertEqual({'name': 'dummy-repo'}, conf.get('ecr_repo'))

    @mock_dynamodb2
    def test_set_config_placement_constraints(self):
        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'secrets_name': 'secret-config',
                        'command': None,
                        'placement_constraints': [
                            {
                                'type': 'memberOf',
                                'expression': 'expr'
                            }
                        ]
                    }
                }
            })
        except UnrecoverableException as e:
            self.fail('Exception thrown: {}'.format(e))

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'secrets_name': 'secret-config',
                        'command': None,
                        'placement_constraints': [{
                            'type': 'invalid'
                        }]
                    }
                }
            })
            self.fail('Validation error expected but validation passed')
        except UnrecoverableException as e:
            self.assertTrue("'invalid' is not one of ['memberOf', 'distinctInstance']" in str(e))

    @mock_dynamodb2
    def test_set_config_system_controls(self):
        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'system_controls': [
                            {
                                'namespace': 'ns',
                                'value': 'val'
                            }
                        ]
                    }
                }
            })
        except UnrecoverableException as e:
            self.fail('Exception thrown: {}'.format(e))

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'system_controls': "invalid"
                    }
                }
            })
            self.fail('Validation error expected but validation passed')
        except UnrecoverableException as e:
            self.assertTrue("'invalid' is not of type 'array'" in str(e))

    @mock_dynamodb2
    def test_set_config_http_interface(self):
        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'http_interface': {
                            'internal': True,
                            'container_port': 8080,
                            'restrict_access_to': ['0.0.0.0/0'],
                        }
                    }
                }
            })
        except UnrecoverableException as e:
            self.fail('Exception thrown: {}'.format(e))

    @mock_dynamodb2
    def test_set_config_health_check_command(self):
        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'http_interface': {
                            'internal': True,
                            'container_port': 8080,
                            'restrict_access_to': ['0.0.0.0/0'],
                        },
                        "container_health_check": {
                            "command": "echo 'Working'",
                            "start_period": 30,
                            "retries": 4,
                            "interval": 5,
                            "timeout": 30,
                        }
                    }
                }
            })
        except UnrecoverableException as e:
            self.fail('Exception thrown: {}'.format(e))

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'http_interface': {
                            'internal': True,
                            'container_port': 8080,
                            'restrict_access_to': ['0.0.0.0/0'],
                        },
                        "container_health_check": {
                            "start_period": 123,
                        }
                    }
                }
            })
            self.fail('Exception expected but did not fail')
        except UnrecoverableException as e:
            self.assertTrue(True)

    @mock_dynamodb2
    def test_sidecars(self):
        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'sidecars': [
                            {
                                'name': 'redis',
                                'image': 'redis:latest',
                                'memory_reservation': 128
                            },
                            {
                                'name': 'envoy',
                                'image': 'envoy:latest',
                                'memory_reservation': 256,
                                'command': ['./start']
                            }
                        ]
                    }
                }
            })
        except UnrecoverableException as e:
            self.fail('Exception thrown: {}'.format(e))

    @mock_dynamodb2
    def test_container_labels(self):
        service = ServiceConfiguration('test-service', 'test')

        with self.assertRaises(UnrecoverableException) as error:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        "container_labels": {
                            "key": 1
                        }
                    }
                }
            })

        self.assertEqual(
            "1 is not of type 'string' in services.TestService.container_labels.key",
            error.exception.value)

        service._validate_changes({
            'cloudlift_version': 'test',
            'ecr_repo': {'name': 'test-service-repo'},
            'services': {
                'TestService': {
                    'memory_reservation': 1000,
                    'command': None,
                    'secrets_name': 'secret-config',
                    "container_labels": {
                        "key": "value"
                    }
                }
            }
        })

    @mock_dynamodb2
    def test_set_service_and_task_roles(self):
        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'ecr_repo': {'name': 'test-service-repo'},
                'service_role_arn': 'foo',
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'secrets_name': 'secret-config',
                        'http_interface': {
                            'internal': True,
                            'container_port': 8080,
                            'restrict_access_to': ['0.0.0.0/0'],
                        }
                    },
                    'task_arn': 'task_arn',
                    'task_execution_arn': 'task_execution_arn'
                }
            })
        except UnrecoverableException as e:
            self.fail('Exception thrown: {}'.format(e))

    def test_get_random_available_listener_rule_priority(self):
        testing_rules = set(list(range(1, 500)) + list(range(534, 678)) + list(range(1000, 30000)) +
                            list(range(40000, 48000)))
        available_rules = set(range(1, 50001)) - testing_rules
        testing_listener_rules = [{"Priority": rule} for rule in testing_rules]
        for test_iteration in range(1, 100):
            assert ServiceConfiguration._get_random_available_listener_rule_priority(testing_listener_rules, "abcd") not in testing_rules

    def test_get_random_available_listener_priority_raises_exection(self):
        testing_listener_rules = [{"Priority": rule} for rule in range(1, 50001)]
        self.assertRaises(UnrecoverableException, ServiceConfiguration._get_random_available_listener_rule_priority, testing_listener_rules, "abcd")
