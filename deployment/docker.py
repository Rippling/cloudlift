import subprocess
import os

from deployment.logging import log_bold, log_err, log_intent, log_warning


def pull_image(image_uri):
    return subprocess.call([
        "docker",
        "pull",
        image_uri
    ])

def build_image(image_name, context_dir, cache_image_name):
    # TODO refactor
    ssh_key = subprocess.check_output(['cat', os.path.expanduser('~/.ssh/id_rsa')])
    ssh_key = ssh_key.decode('UTF-8')

    subprocess.check_call([
        "docker",
        "build",
        "--cache-from",
        cache_image_name,
        "--build-arg",
        "SSH_KEY="+ssh_key+"",
        "-t",
        image_name,
        context_dir
    ])


def push_image(local_name, remote_name):
    try:
        subprocess.check_call(["docker", "tag", local_name, remote_name])
    except:
        log_err("Local image was not found.")
        exit(1)
    subprocess.check_call(["docker", "push", remote_name])
    subprocess.check_call(["docker", "rmi", remote_name])


def login(user, auth_token, url):
    subprocess.check_call(["docker", "login", "-u", user,
                           "-p", auth_token, url])
