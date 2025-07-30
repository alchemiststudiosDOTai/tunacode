import logging
import os
import shutil

from tunacode.core.logging import setup_logging
from tunacode.core.logging.handlers import RichHandler, StructuredFileHandler


def test_setup_logging_loads_config(tmp_path):
    # Copy the default config to a temp location
    config_src = os.path.join(
        os.path.dirname(__file__), "..", "src", "tunacode", "config", "logging.yaml"
    )
    config_dst = tmp_path / "logging.yaml"
    shutil.copyfile(config_src, config_dst)
    # Should not raise
    setup_logging(str(config_dst))


def test_rich_handler_emits():
    logger = logging.getLogger("test.rich")
    handler = RichHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("This is an info message")
        logger.warning("This is a warning")
        logger.error("This is an error")
        logger.log(25, "This is a thought")
    finally:
        logger.removeHandler(handler)


def test_structured_file_handler_emits(tmp_path):
    log_path = tmp_path / "test_structured.jsonl"
    handler = StructuredFileHandler(str(log_path))
    logger = logging.getLogger("test.structured")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("Structured log message", extra={"extra": {"foo": "bar"}})
    finally:
        logger.removeHandler(handler)
    # Check file was written
    assert log_path.exists()
    with open(log_path) as f:
        lines = f.readlines()
    assert any("Structured log message" in line for line in lines)
