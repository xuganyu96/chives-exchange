import os
from chives.configs.default_config import DEFAULT_CONFIG

def environment_overwrite(config: dict) -> dict:
    """Given a dictionary, return a copy where for each of its key, the value 
    is overwritten by environment variable if there is one

    :param config: the original configuration dictionary
    :type config: dict
    :return: a copy of the original configuration dictionary but overwritten by 
    the 
    :rtype: dict
    """
    return {k: os.getenv(k, v) for k, v in config.items()}
