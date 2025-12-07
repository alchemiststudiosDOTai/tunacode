import logging
from typing import Any

# Custom log level: THOUGHT
THOUGHT = 25
logging.addLevelName(THOUGHT, "THOUGHT")


def thought(self: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(THOUGHT):
        self._log(THOUGHT, message, args, **kwargs)


logging.Logger.thought = thought


def setup_logging(config_path=None):
    """
    Set up logging configuration from YAML file.
    """
    from .config import LogConfig

    LogConfig.load(config_path)
