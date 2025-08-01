import logging
import logging.config
import os

import yaml

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "logging.yaml"
)


class LogConfig:
    @staticmethod
    def load(config_path=None):
        """
        Load logging configuration from YAML file and apply it.
        """
        path = config_path or DEFAULT_CONFIG_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(f"Logging config file not found: {path}")
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        logging_config = config.get("logging", config)
        try:
            logging.config.dictConfig(logging_config)
        except Exception as e:
            print(f"Failed to configure logging: {e}")
            logging.basicConfig(level=logging.INFO)
