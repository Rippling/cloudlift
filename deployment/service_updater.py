import base64
import multiprocessing
import os
import subprocess
import sys
import boto3
import getpass
from time import sleep

from botocore.exceptions import ClientError
from stringcase import spinalcase

from config import region as region_service
from config.account import get_account_id
from config.region import (get_client_for,
                           get_region_for_environment)
from config.stack import get_cluster_name, get_service_stack_name
from deployment import deployer
from deployment.ecs import EcsClient
from deployment.logging import log_bold, log_err, log_intent, log_warning
import deployment.git as git
import deployment.docker as docker

DEPLOYMENT_COLORS = ['blue', 'magenta', 'white', 'cyan']


class ServiceUpdater(object):
    def __init__(self, name, environment, env_sample_file, version=None,
                 working_dir='.'):
        self.name = name
        self.environment = environment
        if env_sample_file is not None:
            self.env_sample_file = env_sample_file
        else:
            self.env_sample_file = './env.sample'
        self.version = version
        # self.ecr_client = boto3.session.Session(region_name=self.region).client('ecr')
        # self.cluster_name = get_cluster_name(environment)
        self.working_dir = working_dir

    @property
    def cluster_name(self):
        return get_cluster_name(self.environment)

    @property
    def ecr_client(self):
        return boto3.session.Session(region_name=self.region).client('ecr')

    def run(self):
        log_warning("Deploying to {self.region}".format(**locals()))
        self.init_stack_info()
        if not os.path.exists(self.env_sample_file):
            log_err('env.sample not found. Exiting.')
            exit(1)
        log_intent("name: " + self.name + " | environment: " +
                   self.environment + " | version: " + str(self.version))
        # log_bold("Checking image in ECR")
        # self.upload_artefacts()
        log_bold("Initiating deployment\n")
        ecs_client = EcsClient(None, None, self.region)
        jobs = []
        for index, service_name in enumerate(self.ecs_service_names):
            log_bold("Starting to deploy " + service_name)
            color = DEPLOYMENT_COLORS[index % 3]
            image_url = self.ecr_image_uri
            image_url += (':' + self.version)
            process = multiprocessing.Process(
                target=deployer.deploy_new_version,
                args=(
                    ecs_client,
                    self.cluster_name,
                    service_name,
                    self.version,
                    self.name,
                    self.env_sample_file,
                    self.environment,
                    color,
                    image_url
                )
            )
            jobs.append(process)
            process.start()

        exit_codes = []
        while True:
            sleep(1)
            exit_codes = [proc.exitcode for proc in jobs]
            if None not in exit_codes:
                break

        if any(exit_codes) != 0:
            sys.exit(1)

    def upload_image(self, additional_tags, force_update):
        self.upload_artefacts(force_update)
        # tag = self.get_tag()
        for new_tag in additional_tags:
            self._add_image_tag(self.version, new_tag)

    # Check out a corresponding version and build
    def build_image(self):
        # tag = self.get_tag()
        image_name = spinalcase(self.name) + ':' + self.version
        log_bold("Building docker image " + image_name)
        # switch to the version
        current_branch = git.get_current_branch()
        log_bold("Current branch is {}. Checking out {} for build.".format(current_branch, self.version))
        git.checkout(self.version)
        # pull latest (for cache)
        self._login_to_ecr()
        latest_master_ecr_uri = self.ecr_image_uri + ':master'
        docker.pull_image(latest_master_ecr_uri)
        # build
        docker.build_image(image_name, self.working_dir,
                           cache_image_name=latest_master_ecr_uri)
        # switch back
        git.checkout(current_branch)
        log_bold("Built " + image_name)

    def upload_artefacts(self, force_update):
        self.ensure_repository()
        self.ensure_image_in_ecr(force_update)

    def ensure_repository(self):
        try:
            self.ecr_client.create_repository(
                repositoryName=self.repo_name,
                imageScanningConfiguration={
                    'scanOnPush': True
                },
            )
            log_intent('Repo created with name: '+self.repo_name)
        except Exception as ex:
            if type(ex).__name__ == 'RepositoryAlreadyExistsException':
                log_intent('Repo exists with name: '+self.repo_name)
            else:
                raise ex

    def _login_to_ecr(self):
        log_intent("Attempting login...")
        auth_token_res = self.ecr_client.get_authorization_token()
        user, auth_token = base64.b64decode(
            auth_token_res['authorizationData'][0]['authorizationToken']
        ).decode("utf-8").split(':')
        ecr_url = auth_token_res['authorizationData'][0]['proxyEndpoint']
        docker.login(user, auth_token, ecr_url)
        log_intent('Docker login to ECR succeeded.')

    def push_image(self):
        # tag = self.get_tag()
        version = self.version
        image_name = spinalcase(self.name) + ':' + version
        ecr_name = self.ecr_image_uri + ':' + version
        self._login_to_ecr()
        docker.push_image(image_name, ecr_name)
        log_intent('Pushed the image (' + image_name + ') to (' + ecr_name + ') successfully.')

    def _add_image_tag(self, existing_tag, new_tag):
        if existing_tag == new_tag:
            return
        try:
            image = self._find_image_in_ecr(existing_tag)
            image_manifest = image['imageManifest']
            self.ecr_client.put_image(
                repositoryName=self.repo_name,
                imageTag=new_tag,
                imageManifest=image_manifest
            )
            log_intent("Added additional tag {} to existing image {}".format(
                str(new_tag),
                str(existing_tag))
            )
        except:
            log_err("Unable to add additional tag {} to existing image {}".format(
                str(new_tag),
                str(existing_tag))
            )

    def _find_image_in_ecr(self, tag):
        try:
            return self.ecr_client.batch_get_image(
                repositoryName=self.repo_name,
                imageIds=[{'imageTag': tag}]
            )['images'][0]
        except:
            return None

    def ensure_image_in_ecr(self, force_update):
        tag = self.get_tag()
        log_intent("Determined Docker tag " + tag + " based on the current repo state")
        image = self._find_image_in_ecr(tag)
        if image and not force_update:
            log_intent("Image found in ECR. Done.")
        else:
            log_bold("Image not found in ECR. Building image")
            self.build_image()
            self.push_image()
        self._add_image_tag(self.version, tag)

    def generate_task_definition(self, taskdefinition):
        tag = self.get_tag()
        log_intent("name: " + self.name
                   + " | environment: " + self.environment
                   + " | tag: " + str(tag))
        ecs_client = EcsClient(None, None, self.region)
        image_url = self.ecr_image_uri
        image_url += (':' + tag)
        return deployer.build_new_task_definition(
            ecs_client,
            self.cluster_name,
            self.version,
            self.name,
            taskdefinition,
            self.env_sample_file,
            self.environment,
            image_url)

    def get_tag(self):
        commit_sha = git.find_commit_sha(self.version)
        is_dirty = git.is_dirty()
        if self.version and is_dirty:
            log_err("Local copy is dirty. Please commit your changes first.")
            exit(1)
        if is_dirty:
            commit_sha += "-dirty-" + getpass.getuser()
        return commit_sha

    @property
    def ecr_image_uri(self):
        return str(self.account_id) + ".dkr.ecr." + self.region + \
            ".amazonaws.com/" + self.repo_name

    @property
    def repo_name(self):
        return self.name + '-repo'

    @property
    def region(self):
        return get_region_for_environment(self.environment)

    @property
    def account_id(self):
        return get_account_id()

    def init_stack_info(self):
        try:
            self.stack_name = get_service_stack_name(self.environment, self.name)
            stack = get_client_for(
                'cloudformation',
                self.environment
            ).describe_stacks(
                StackName=self.stack_name
            )['Stacks'][0]
            self.ecs_service_names = [
                service_name['OutputValue'] for service_name in list(
                    filter(
                        lambda x: x['OutputKey'].endswith('EcsServiceName'),
                        stack['Outputs']
                    )
                )
            ]
        except ClientError as client_error:
            err = str(client_error)
            if "Stack with id %s does not exist" % self.stack_name in err:
                log_err(
                    "%s cluster not found. Create the environment cluster using `create_environment` command." % self.environment)
            else:
                log_err(str(client_error))
            exit(1)
