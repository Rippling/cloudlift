import functools

import boto3
import click
from botocore.exceptions import ClientError

from config import editor
from config.banner import highlight_production
from deployment.configs import deduce_name
from deployment.environment_creator import EnvironmentCreator
from deployment.logging import log_err
from deployment.service_creator import ServiceCreator
from deployment.service_information_fetcher import ServiceInformationFetcher
from deployment.service_updater import ServiceUpdater
from session.session_creator import SessionCreator
from version import VERSION


def _require_environment(func):
    @click.option('--environment', '-e', prompt='environment',
                  help='environment')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs['environment'] == 'production':
            highlight_production()
        return func(*args, **kwargs)
    return wrapper


def _require_name(func):
    @click.option('--name', help='Your service name, give the name of \
repo')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if kwargs['name'] is None:
            kwargs['name'] = deduce_name(None)
        return func(*args, **kwargs)
    return wrapper


@click.group()
@click.version_option(version=VERSION, prog_name="cloudlift")
def cli():
    """
        Cloudlift is built by Simpl developers to make it easier to launch \
        dockerized services in AWS ECS.
    """
    try:
        boto3.client('cloudformation')
    except ClientError:
        log_err("Could not connect to AWS!")
        log_err("Ensure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY & \
AWS_DEFAULT_REGION env vars are set OR run 'aws configure'")
        exit(1)


@cli.command(help="Create a new service. This can contain multiple \
ECS services")
@_require_environment
@_require_name
def create_service(name, environment):
    ServiceCreator(name, environment).create()


@cli.command(help="Update existing service.")
@_require_environment
@_require_name
def update_service(name, environment):
    ServiceCreator(name, environment).update()


@cli.command(help="Create a new environment")
@click.option('--environment', '-e', prompt='environment',
              help='environment')
def create_environment(environment):
    EnvironmentCreator(environment).run()


@cli.command(help="Update environment")
@_require_environment
@click.option('--update_ecs_agents',
              is_flag=True,
              help='Update ECS container agents')
def update_environment(environment, update_ecs_agents):
    EnvironmentCreator(environment).run_update(update_ecs_agents)


@cli.command(help="Command used to create or update the configuration \
in parameter store")
@_require_name
@_require_environment
def edit_config(name, environment):
    editor.edit_config(name, environment)


@cli.command()
@_require_environment
@_require_name
@click.option('--version', default=None, help='Git commit sha, branch, tag')
@click.option('--upload', default=False, help='Build/upload to ECR first')
def deploy_service(name, environment, version, upload):
    ServiceUpdater(name, environment, None, version).run(upload)


@cli.command()
@click.option('--version', default=None, help='Git commit sha, branch, tag')
@click.option('--force_update', default=False, help='Rebuild if already exists')
@click.option('--additional_tags', default=[], multiple=True,
              help='Additional tags for the image apart from commit SHA')
@_require_name
@_require_environment
def upload_to_ecr(name, environment, version, additional_tags, force_update):
    ServiceUpdater(name, environment, '', version).upload_image(additional_tags, force_update)


@cli.command(help="Get commit information of currently deployed code \
from commit hash")
@_require_environment
@_require_name
@click.option('--short', '-s', is_flag=True,
              help='Pass this when you just need the version tag')
def get_version(name, environment, short):
    ServiceInformationFetcher(name, environment).get_version(short)


@cli.command(help="Start SSH session in instance running a current \
service task")
@_require_environment
@_require_name
@click.option('--mfa', help='MFA code', prompt='MFA Code')
def start_session(name, environment, mfa):
    SessionCreator(name, environment).start_session(mfa)


'''
New commands
'''


@cli.command(help="Get Docker tag")
@_require_name
@click.option('--version', default=None, help='Git commit sha, branch, tag')
def get_tag(name, version):
    print(ServiceUpdater(name, '', '', version).get_tag())


@cli.command(help="Build Docker image")
@_require_name
@click.option('--version', default=None, help='Git commit sha, branch, tag')
def build_image(name, version):
    ServiceUpdater(name, '', '', version).build_image()


@cli.command(help="Push Docker image")
@_require_name
@_require_environment
@click.option('--version', default=None, help='Git commit sha, branch, tag')
def push_image(name, environment, version):
    ServiceUpdater(name, environment, '', version).push_image()


@cli.command(help="Get new ECS TaskDefinition based on code + param changes")
@_require_environment
@_require_name
@click.option('--version', default=None, help='Git commit sha, branch, tag')
@click.option('--taskdefinition', '-t', help='Existing ECS taskdefinition name')
def make_task_definition(name, taskdefinition, environment, version):
    # 25 supported properties of RegisterTaskDefinitionRequest
    properties = ["requiresCompatibilities", "customQueryParameters", "taskRoleArn", "requestClientOptions",
                  "customRequestHeaders", "generalProgressListener", "sdkRequestTimeout", "requestCredentials",
                  "requestMetricCollector", "executionRoleArn", "networkMode", "cloneSource", "volumes",
                  "requestCredentialsProvider", "containerDefinitions", "memory", "family", "cpu",
                  "sdkClientExecutionTimeout", "placementConstraints", "tags", "ipcMode", "pidMode",
                  "proxyConfiguration", "inferenceAccelerators"]
    task_definition = ServiceUpdater(name, environment, None, version).generate_task_definition(taskdefinition)
    filtered_task_definition = {property: task_definition[property] for property in properties if
                                property in task_definition}
    import json
    # this won't cover local dirty project
    filename = "task_definition.json"
    if version:
        filename = "task_definition-{}-{}.json".format(version, environment)
    f = open(filename, "w")
    f.write(json.dumps(filtered_task_definition))
    f.close()


if __name__ == '__main__':
    cli()
