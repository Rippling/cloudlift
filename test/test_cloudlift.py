import os
import time

import boto3
import requests
import urllib3
from mock import patch
import json

from cloudlift.config import ServiceConfiguration, VERSION
from cloudlift.deployment.service_creator import ServiceCreator
from cloudlift.deployment.service_updater import ServiceUpdater
from pathlib import Path
from cloudlift.config import secrets_manager

TEST_DIR = Path(__file__).resolve().parent


def setup_module(module):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


environment_name = 'ci'
service_name = 'cfn-dummy'


def mocked_service_config(cls, *args, **kwargs):
    return {
        "cloudlift_version": VERSION,
        'ecr_repo': {'name': 'dummy-repo'},
        "services": {
            "Dummy": {
                "command": None,
                "secrets_name": "{}-{}".format(service_name, environment_name),
                "sidecars": [
                    {"name": "redis", "image": "redis", "memory_reservation": 256}
                ],
                "http_interface": {
                    "alb": {
                        "create_new": True
                    },
                    "container_port": 80,
                    "internal": False,
                    "restrict_access_to": [
                        "0.0.0.0/0"
                    ],
                    "health_check_path": "/elb-check"
                },
                "task_role_attached_managed_policy_arns": ["arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"],
                "memory_reservation": 512
            }
        }
    }


def mocked_service_with_secrets_manager_config(cls, *args, **kwargs):
    return {
        "cloudlift_version": VERSION,
        'ecr_repo': {'name': 'dummy-repo'},
        "services": {
            "Dummy": {
                "command": None,
                "secrets_name": "{}-{}".format(service_name, environment_name),
                "sidecars": [
                    {"name": "redis", "image": "redis", "memory_reservation": 256}
                ],
                "http_interface": {
                    "alb": {
                        "create_new": True
                    },
                    "container_port": 80,
                    "internal": False,
                    "restrict_access_to": [
                        "0.0.0.0/0"
                    ],
                    "health_check_path": "/elb-check"
                },
                "task_role_attached_managed_policy_arns": ["arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"],
                "memory_reservation": 512
            }
        }
    }


def test_cloudlift_can_deploy_to_ec2(keep_resources):
    cfn_client = boto3.client('cloudformation')
    stack_name = f'{service_name}-{environment_name}'
    cfn_client.delete_stack(StackName=stack_name)
    print("initiated delete")
    waiter = cfn_client.get_waiter('stack_delete_complete')
    waiter.wait(StackName=stack_name)
    print("completed delete")
    os.chdir(f'{TEST_DIR}/dummy')
    print("adding configuration to parameter store")
    _set_param_store_env(environment_name, service_name, {'PORT': '80', 'LABEL': 'Demo', 'REDIS_HOST': 'redis'})
    print("adding configuration to secrets manager")
    _set_secrets_manager_config(f"{service_name}-{environment_name}", {'LABEL': 'Value from secret manager'})

    ServiceCreator(service_name, environment_name, "env.sample").create(
        mocked_service_with_secrets_manager_config(None)
    )

    ServiceUpdater(service_name, environment_name, "env.sample", timeout_seconds=600).run()
    outputs = cfn_client.describe_stacks(StackName=stack_name)['Stacks'][0]['Outputs']
    service_url = [x for x in outputs if x["OutputKey"] == "DummyURL"][0]['OutputValue']
    expected = 'This is dummy app. Label: Value from secret manager. Redis PING: PONG. AWS EC2 READ ACCESS: True'
    content_matched = wait_until(lambda: match_page_content(service_url, expected), 60)
    assert content_matched
    if not keep_resources:
        cfn_client.delete_stack(StackName=stack_name)


def test_cloudlift_can_deploy_to_ec2_with_editable_config(keep_resources):
    cfn_client = boto3.client('cloudformation')
    stack_name = f'{service_name}-{environment_name}'
    cfn_client.delete_stack(StackName=stack_name)
    print("initiated delete")
    waiter = cfn_client.get_waiter('stack_delete_complete')
    waiter.wait(StackName=stack_name)
    print("completed delete")
    os.chdir(f'{TEST_DIR}/dummy')
    print("adding configuration to parameter store")
    _set_param_store_env(environment_name, service_name, {'PORT': '80', 'LABEL': 'Demo', 'REDIS_HOST': 'redis'})
    print("adding configuration to secrets manager")
    _set_secrets_manager_config(f"{service_name}-{environment_name}", {})
    with patch.object(ServiceConfiguration, 'edit_config',
                      new=mocked_service_config):
        with patch.object(ServiceConfiguration, 'get_config',
                          new=mocked_service_config):
            ServiceCreator(service_name, environment_name, "env.sample").create()

    ServiceUpdater(service_name, environment_name, "env.sample", timeout_seconds=600).run()
    outputs = cfn_client.describe_stacks(StackName=stack_name)['Stacks'][0]['Outputs']
    service_url = [x for x in outputs if x["OutputKey"] == "DummyURL"][0]['OutputValue']
    content_matched = wait_until(lambda: match_page_content(service_url, 'This is dummy app. Label: Demo. Redis '
                                                                         'PING: PONG. AWS EC2 READ ACCESS: True'), 60)
    assert content_matched
    if not keep_resources:
        cfn_client.delete_stack(StackName=stack_name)


def test_cloudlift_service_with_secrets_manager_config(keep_resources):
    cfn_client = boto3.client('cloudformation')
    stack_name = f'{service_name}-{environment_name}'
    cfn_client.delete_stack(StackName=stack_name)
    print("initiated delete")
    waiter = cfn_client.get_waiter('stack_delete_complete')
    waiter.wait(StackName=stack_name)
    print("completed delete")
    os.chdir(f'{TEST_DIR}/dummy')
    print("adding configuration to parameter store")
    _set_param_store_env(environment_name, service_name, {'PORT': '80', 'LABEL': 'Demo', 'REDIS_HOST': 'redis'})
    print("adding configuration to secrets manager")
    _set_secrets_manager_config(f"{service_name}-{environment_name}", {'LABEL': 'Value from secret manager v1'})
    with patch.object(ServiceConfiguration, 'edit_config',
                      new=mocked_service_with_secrets_manager_config):
        with patch.object(ServiceConfiguration, 'get_config',
                          new=mocked_service_with_secrets_manager_config):
            ServiceCreator(service_name, environment_name, "env.sample").create()

    outputs = cfn_client.describe_stacks(StackName=stack_name)['Stacks'][0]['Outputs']
    service_url = [x for x in outputs if x["OutputKey"] == "DummyURL"][0]['OutputValue']

    expected = 'This is dummy app. Label: Value from secret manager v1. Redis PING: PONG. AWS EC2 READ ACCESS: True'
    content_matched = wait_until(lambda: match_page_content(service_url, expected), 60)
    assert content_matched

    print("modifying configuration in secrets manager")
    _set_secrets_manager_config(f"{service_name}-{environment_name}", {'LABEL': 'Value from secret manager v2'})
    secrets_manager.clear_cache()

    ServiceUpdater(service_name, environment_name, "env.sample", timeout_seconds=600).run()
    expected = 'This is dummy app. Label: Value from secret manager v2. Redis PING: PONG. AWS EC2 READ ACCESS: True'
    content_matched = wait_until(lambda: match_page_content(service_url, expected), 60)
    assert content_matched

    if not keep_resources:
        cfn_client.delete_stack(StackName=stack_name)


def match_page_content(service_url, content_expected):
    page_content = requests.get(service_url, verify=False).text
    print("page_content: " + str(page_content))
    print("expected: " + content_expected)
    return page_content.strip() == content_expected.strip()


def wait_until(predicate, timeout, period=1, *args, **kwargs):
    mustend = time.time() + timeout
    while time.time() < mustend:
        if predicate(*args, **kwargs):
            return True
        print("sleeping and gonna retry...")
        time.sleep(period)
    return False


def _set_param_store_env(env_name, svc_name, env_config):
    ssm_client = boto3.client('ssm')
    for env_var in env_config:
        ssm_client.put_parameter(
            Name=f"/{env_name}/{svc_name}/{env_var}",
            Value=env_config[env_var],
            Type="SecureString",
            KeyId='alias/aws/ssm', Overwrite=True
        )


def _set_secrets_manager_config(secret_name, config):
    client = boto3.client('secretsmanager')
    secret_string = json.dumps(config)
    try:
        client.put_secret_value(SecretId=secret_name, SecretString=secret_string)
    except client.exceptions.ResourceNotFoundException:
        client.create_secret(Name=secret_name, SecretString=secret_string)
