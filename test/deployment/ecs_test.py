import unittest
from cloudlift.deployment.ecs import EcsTaskDefinition


class TestEcsTaskDefinition(unittest.TestCase):
    def test_apply_container_environment(self):
        image = '408750594584.dkr.ecr.us-west-2.amazonaws.com/dummy-repo:eb3089ccc48b5fa8081d296ab81457759fb9995d'
        td = EcsTaskDefinition({'taskDefinitionArn': 'arn:aws:ecs:us-west-2:408750594584:task-definition/DummyFamily:4',
                           'containerDefinitions': [{'name': 'DummyContainer',
                                                     'image': image,
                                                     'cpu': 0, 'memoryReservation': 1000, 'links': [], 'portMappings': [
                                   {'containerPort': 80, 'hostPort': 0, 'protocol': 'tcp'}], 'essential': True,
                                                     'entryPoint': [], 'command': [],
                                                     'environment': [{'name': 'PORT', 'value': '80'},
                                                                     {'name': 'LABEL', 'value': 'L3'}],
                                                     'logConfiguration': {'logDriver': 'awslogs',
                                                                          'secretOptions': []}, 'systemControls': []}],
                           'family': 'DummyFamily',
                           'taskRoleArn': 'arn:aws:iam::408750594584:role/dummy-test-DummyRole-BEXNIBTBTB33',
                           'revision': 4, 'volumes': [], 'status': 'ACTIVE',
                           'requiresAttributes': [{'name': 'com.amazonaws.ecs.capability.logging-driver.awslogs'},
                                                  {'name': 'com.amazonaws.ecs.capability.ecr-auth'},],
                           'placementConstraints': [], 'compatibilities': ['EC2']})

        new_env_config = [{"Name": 'PORT', "Value": '80'}, {"Name": 'LABEL', "Value": 'L4'}]
        td.apply_container_environment(td.containers[0], new_env_config)

        expected_updated_env = [{'name': 'PORT', 'value': '80'}, {'name': 'LABEL', 'value': 'L4'}]
        self.assertEqual(td.containers[0]['environment'], expected_updated_env)
        self.assertEqual(len(td.diff), 1)
        diff = td.diff[0]
        self.assertEqual(diff.container, 'DummyContainer')
        self.assertEqual(diff.field, 'environment')
        self.assertEqual(diff.value, {'LABEL': 'L4', 'PORT': '80'})
        self.assertEqual(diff.old_value, {'LABEL': 'L3', 'PORT': '80'})
