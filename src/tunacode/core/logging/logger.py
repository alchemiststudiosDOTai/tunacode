import logging


def get_logger(name=None):
    """
    Get a logger instance with the given name.
    """
    return logging.getLogger(name)
