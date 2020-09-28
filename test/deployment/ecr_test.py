from cloudlift.deployment import ECR
from unittest import TestCase
import boto3
from unittest.mock import patch, MagicMock


class TestECR(TestCase):
    def setUp(self):
        patcher = patch.object(boto3.session.Session, 'client')
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_build_command_without_build_args(self):
        ecr = ECR("aws-region", "test-repo", "12345", None, None)
        assert 'docker build -t test:v1 .' == ecr._build_command("test:v1")

    def test_build_command_with_build_args(self):
        ecr = ECR("aws-region", "test-repo", "12345", None, None,
                  build_args={"SSH_KEY": "\"`cat ~/.ssh/id_rsa`\"", "A": "1"})
        assert ecr._build_command("test:v1") == 'docker build -t test:v1 --build-arg SSH_KEY="`cat ~/.ssh/id_rsa`"' \
                                                ' --build-arg A=1 .'

    def test_use_dockerfile_with_build_args(self):
        ecr = ECR("aws-region", "test-repo", "12345", None, None,
                  build_args={"SSH_KEY": "\"`cat ~/.ssh/id_rsa`\"", "A": "1"}, dockerfile='CustomDockerfile')
        assert ecr._build_command("test:v1") == 'docker build -f CustomDockerfile -t test:v1 ' \
                                                '--build-arg SSH_KEY="`cat ~/.ssh/id_rsa`" --build-arg A=1 .'

    def test_build_command_with_dockerfile_without_build_args(self):
        ecr = ECR("aws-region", "test-repo", "12345", None, None, dockerfile='CustomDockerfile')
        assert 'docker build -f CustomDockerfile -t test:v1 .' == ecr._build_command("test:v1")

    @patch("boto3.session.Session")
    @patch("boto3.client")
    def test_if_ecr_assumes_given_role_arn(self, mock_boto_client, mock_session):
        assume_role_arn = 'test-assume-role-arn'
        mock_sts_client = MagicMock()
        mock_boto_client.return_value = mock_sts_client
        mock_sts_client.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'mockAccessKeyId', 'SecretAccessKey': 'mockSecretAccessKey',
                'SessionToken': 'mockSessionToken'
            }
        }

        ECR("aws-region", "test-repo", "12345", assume_role_arn=assume_role_arn)

        mock_sts_client.assume_role.assert_called_with(RoleArn=assume_role_arn, RoleSessionName='ecrCloudliftAgent')
        mock_session.assert_called_with(
            aws_access_key_id='mockAccessKeyId',
            aws_secret_access_key='mockSecretAccessKey',
            aws_session_token='mockSessionToken',
        )

    @patch("cloudlift.deployment.ecr._create_ecr_client")
    def test_ensure_repository(self, mock_create_ecr_client):
        mock_ecr_client = MagicMock()
        mock_create_ecr_client.return_value = mock_ecr_client

        ecr = ECR("aws-region", "test-repo", "12345")

        ecr.ensure_repository()

        mock_ecr_client.create_repository.assert_called_with(
            repositoryName='test-repo',
            imageScanningConfiguration={'scanOnPush': True}
        )