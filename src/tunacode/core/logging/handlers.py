import json
import logging

from rich.console import Console
from rich.text import Text


class RichHandler(logging.Handler):
    """
    Handler that outputs logs to the console using rich formatting.
    """

    level_icons = {
        "INFO": "",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
        "THOUGHT": "🤔",
        "DEBUG": "",
    }

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.console = Console()

    def emit(self, record):
        try:
            icon = self.level_icons.get(record.levelname, "")
            timestamp = self.formatTime(record)
            msg = self.format(record)
            if icon:
                output = f"[{timestamp}] {icon} {msg}"
            else:
                output = f"[{timestamp}] {msg}"
            self.console.print(Text(output))
        except Exception:
            self.handleError(record)

    def formatTime(self, record, datefmt=None):
        from datetime import datetime

        ct = datetime.fromtimestamp(record.created)
        if datefmt:
            return ct.strftime(datefmt)
        return ct.strftime("%Y-%m-%d %H:%M:%S")


class StructuredFileHandler(logging.FileHandler):
    """
    Handler that outputs logs as structured JSON lines.
    """

    def emit(self, record):
        try:
            log_entry = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "name": record.name,
                "line": record.lineno,
                "message": record.getMessage(),
                "extra_data": getattr(record, "extra", {}),
            }
            self.stream.write(json.dumps(log_entry) + "\n")
            self.flush()
        except Exception:
            self.handleError(record)

    def formatTime(self, record, datefmt=None):
        from datetime import datetime, timezone

        ct = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return ct.isoformat()
