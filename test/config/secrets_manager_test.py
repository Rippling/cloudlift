from cloudlift.config import secrets_manager
from mock import patch, MagicMock
import unittest
import datetime
from dateutil.tz.tz import tzlocal


class TestSecretsManager(unittest.TestCase):
    @patch('cloudlift.config.secrets_manager.get_client_for')
    def test_get_config(self, mock_get_client_for):
        get_secret_value_return_value = {
            'ARN': 'arn:aws:secretsmanager:us-west-2:12345678:secret:dummy-test-QvDJsW',
            'Name': 'dummy-test', 'VersionId': 'a1b87fb5-453e-42bd-a4f5-fdc0834854ef',
            'SecretString': '{"PORT":"80","LABEL":"L1"}', 'VersionStages': ['AWSCURRENT'],
            'CreatedDate': datetime.datetime(2020, 9, 2, 15, 20, 37, 944000, tzinfo=tzlocal()),
            'ResponseMetadata': {'RequestId': '17f66dd3-8fad-4dad-a43e-e1ec9c99ef06', 'HTTPStatusCode': 200,
                                 'HTTPHeaders': {'date': 'Thu, 03 Sep 2020 18:01:47 GMT',
                                                 'content-type': 'application/x-amz-json-1.1', 'content-length': '292',
                                                 'connection': 'keep-alive',
                                                 'x-amzn-requestid': '17f66dd3-8fad-4dad-a43e-e1ec9c99ef06'},
                                 'RetryAttempts': 0}}
        mock_client = MagicMock('boto3_client', get_secret_value=MagicMock(return_value=get_secret_value_return_value))
        mock_get_client_for.return_value = mock_client

        config = secrets_manager.get_config("dummy", "test")

        mock_get_client_for.assert_called_once_with('secretsmanager', 'test')
        mock_client.get_secret_value.assert_called_once_with(SecretId='dummy-test')
        expected_config = {
            "PORT": "arn:aws:secretsmanager:us-west-2:12345678:secret:dummy-test-QvDJsW:PORT::a1b87fb5-453e-42bd-a4f5-fdc0834854ef",
            "LABEL": "arn:aws:secretsmanager:us-west-2:12345678:secret:dummy-test-QvDJsW:LABEL::a1b87fb5-453e-42bd-a4f5-fdc0834854ef",
        }
        self.assertEqual(expected_config, config)
