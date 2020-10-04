import multiprocessing
import os
from time import sleep

import boto3

from cloudlift.config import get_account_id
from cloudlift.config import get_cluster_name
from cloudlift.config import (get_region_for_environment)
from cloudlift.config.logging import log_bold, log_intent, log_warning
from cloudlift.deployment import deployer, ServiceInformationFetcher
from cloudlift.deployment.ecs import EcsClient
from cloudlift.exceptions import UnrecoverableException
from cloudlift.utils import chunks
from cloudlift.deployment.ecr import ECR

DEPLOYMENT_COLORS = ['blue', 'magenta', 'white', 'cyan']
DEPLOYMENT_CONCURRENCY = int(os.environ.get('CLOUDLIFT_DEPLOYMENT_CONCURRENCY', 4))


class ServiceUpdater(object):
    def __init__(self, name, environment='', env_sample_file='', timeout_seconds=None, version=None,
                 build_args=None, dockerfile=None, working_dir='.'):
        self.name = name
        self.environment = environment
        self.env_sample_file = env_sample_file
        self.timeout_seconds = timeout_seconds
        self.version = version
        self.ecr_client = boto3.session.Session(region_name=self.region).client('ecr')
        self.cluster_name = get_cluster_name(environment)
        self.service_info_fetcher = ServiceInformationFetcher(self.name, self.environment)
        if not self.service_info_fetcher.stack_found:
            raise UnrecoverableException(
                "error finding stack in ServiceUpdater: {}-{}".format(self.name, self.environment))
        self.ecr = ECR(
            self.region,
            self.service_info_fetcher.ecr_repo_name,
            self.service_info_fetcher.ecr_account_id or get_account_id(),
            self.service_info_fetcher.ecr_assume_role_arn,
            version,
            build_args,
            dockerfile,
            working_dir,
        )

    def run(self):
        log_warning("Deploying to {self.region}".format(**locals()))
        if not os.path.exists(self.env_sample_file):
            raise UnrecoverableException('env.sample not found. Exiting.')
        log_intent("name: " + self.name + " | environment: " +
                   self.environment + " | version: " + str(self.version))
        log_bold("Checking image in ECR")
        self.ecr.upload_artefacts()
        log_bold("Initiating deployment\n")
        ecs_client = EcsClient(None, None, self.region)

        image_url = self.ecr.image_uri
        target = deployer.deploy_new_version
        kwargs = dict(client=ecs_client, cluster_name=self.cluster_name,
                      deploy_version_tag=self.version,
                      service_name=self.name, sample_env_file_path=self.env_sample_file,
                      timeout_seconds=self.timeout_seconds, env_name=self.environment,
                      complete_image_uri=image_url)
        self.run_job_for_all_services("Deploy", target, kwargs)

    def revert(self):
        target = deployer.revert_last_deployment
        ecs_client = EcsClient(None, None, self.region)
        kwargs = dict(client=ecs_client, cluster_name=self.cluster_name, timeout_seconds=self.timeout_seconds)
        self.run_job_for_all_services("Revert", target, kwargs)

    def run_job_for_all_services(self, job_name, target, kwargs):
        log_bold("{} concurrency: {}".format(job_name, DEPLOYMENT_CONCURRENCY))
        jobs = []
        service_info = self.service_info_fetcher.service_info
        for index, ecs_service_logical_name in enumerate(service_info):
            ecs_service_info = service_info[ecs_service_logical_name]
            log_bold(f"Queueing {job_name} of " + ecs_service_info['ecs_service_name'])
            color = DEPLOYMENT_COLORS[index % 3]
            kwargs.update(dict(ecs_service_name=ecs_service_info['ecs_service_name'],
                               secrets_name=ecs_service_info.get('secrets_name'),
                               color=color))
            process = multiprocessing.Process(
                target=target,
                kwargs=kwargs
            )
            jobs.append(process)
        all_exit_codes = []
        for chunk_of_jobs in chunks(jobs, DEPLOYMENT_CONCURRENCY):
            for process in chunk_of_jobs:
                process.start()

            while True:
                sleep(1)
                exit_codes = [proc.exitcode for proc in chunk_of_jobs]
                if None not in exit_codes:
                    break

            for exit_code in exit_codes:
                all_exit_codes.append(exit_code)
        if any(all_exit_codes) != 0:
            raise UnrecoverableException(f"{job_name} failed")

    @property
    def region(self):
        return get_region_for_environment(self.environment)
