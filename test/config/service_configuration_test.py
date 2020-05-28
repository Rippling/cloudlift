import boto3
from moto import mock_dynamodb2

from cloudlift.config import ServiceConfiguration
from cloudlift.version import VERSION
from cloudlift.exceptions import UnrecoverableException

from unittest import TestCase
from unittest.mock import patch, MagicMock


class TestServiceConfiguration(object):
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
                    "services": {
                        "TestService": {
                            "memory_reservation": 1000,
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
                    "services": {
                        "TestService": {
                            "memory_reservation": 1000,
                            "command": None,
                            "http_interface": {
                                "internal": True,
                                "container_port": 80,
                                "restrict_access_to": [u'0.0.0.0/0']
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
                    "services": {
                        "TestService": {
                            "memory_reservation": 1000,
                            "command": None,
                            "http_interface": {
                                "internal": True,
                                "container_port": 80,
                                "restrict_access_to": [u"123.123.123.123/32"]
                            }
                        }
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
                    "services": {
                        "TestService": {
                            "memory_reservation": 1000,
                            "command": None,
                            "http_interface": {
                                "internal": True,
                                "container_port": 80,
                                "restrict_access_to": [u'0.0.0.0/0']
                            },
                            "stop_timeout": 120
                        }
                    }
                }


class TestServiceConfigurationValidation(TestCase):
    @patch("cloudlift.config.service_configuration.get_resource_for")
    def test_set_config_system_controls(self, mock_get_resource_for):
        mock_get_resource_for.return_value = MagicMock()

        service = ServiceConfiguration('test-service', 'test')

        try:
            service._validate_changes({
                'cloudlift_version': 'test',
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
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
                'services': {
                    'TestService': {
                        'memory_reservation': 1000,
                        'command': None,
                        'system_controls': "invalid"
                    }
                }
            })
            self.fail('Validation error expected but validation passed')
        except UnrecoverableException as e:
            self.assertTrue("'invalid' is not of type 'array'" in str(e))
