from cloudlift.config import get_client_for
from cloudlift.config.logging import log
import json


def get_config(config_prefix, env):
    response = get_client_for('secretsmanager', env).get_secret_value(SecretId=f"${config_prefix}-{env}")
    log(f"Fetched config from AWS secrets manager. Version: ${response['VersionId']}")
    return json.loads(response['SecretString'])