import subprocess
import os

from deployment.logging import log_bold, log_err, log_intent, log_warning


def pull_image(image_uri):
    return subprocess.call([
        "docker",
        "pull",
        image_uri
    ])

def build_image(image_name, context_dir, cache_image_name, build_args):
    build_command = ["docker", "build"]

    if cache_image_name:
        build_command += ["--cache-from", cache_image_name]

    if build_args:
        for k, v in build_args.items():
            build_command += ["--build-arg", "=".join((k, v))]

    build_command += ["-t", image_name, context_dir]

    subprocess.check_call(build_command)


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
