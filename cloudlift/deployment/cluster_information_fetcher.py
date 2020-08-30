from cloudlift.config import get_client_for, get_cluster_name


def fetch_ec2_hosts_sg(environment):
    client = get_client_for('cloudformation', environment)
    return client.describe_stack_resources(
        StackName=get_cluster_name(environment),
        LogicalResourceId='SecurityGroupEc2Hosts')['StackResources'][0]['PhysicalResourceId']
