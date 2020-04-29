import subprocess

from deployment.logging import log_bold, log_err, log_intent, log_warning


def checkout(version):
    # commit_sha = find_commit_sha(version)
    try:
        subprocess.call(
            ["git", "checkout", version],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
    except:
        log_err("Could not check out given version (tag, branch or commit SHA): %s" % version)
        exit(1)


def get_current_branch():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        ).strip().decode("utf-8")
    except:
        log_err("Failed to get current branch")
        exit(1)


def is_dirty():
    return True \
        if subprocess.check_output(["git", "status", "--short"]).decode("utf-8") \
        else False


def find_commit_sha(version=None):
    # log_intent("Finding commit SHA")
    try:
        version_to_find = version or "HEAD"
        commit_sha = subprocess.check_output(
            ["git", "rev-list", "-n", "1", version_to_find]
        ).strip().decode("utf-8")
        # log_intent("Found commit SHA " + commit_sha)
        return commit_sha
    except:
        log_err("Commit SHA not found. Given version is not a git tag, branch or commit SHA")
        exit(1)
