from os import getcwd, path

import stringcase

from cloudlift.config.logging import log_bold


def deduce_name(name):
    if name is None:
        name = __sanitized_dirname()
        log_bold("Assuming the service name to be: " + name)
    return stringcase.spinalcase(name)


def __sanitized_dirname():
    return path.basename(getcwd())
