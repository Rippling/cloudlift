from cloudlift.config import get_client_for
from cloudlift.config.logging import log
import json


def get_config(name_prefix, env):
    response = get_client_for('secretsmanager', env).get_secret_value(SecretId=f"{name_prefix}-{env}")
    log(f"Fetched config from AWS secrets manager. Version: {response['VersionId']}")
    secret_val = json.loads(response['SecretString'])
    return {k: f"{response['ARN']}:{k}::{response['VersionId']}" for k in secret_val}
