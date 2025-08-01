import logging


class SimpleFormatter(logging.Formatter):
    """
    Simple formatter for UI output.
    """

    def __init__(self):
        super().__init__("[%(levelname)s] %(message)s")


class DetailedFormatter(logging.Formatter):
    """
    Detailed formatter for backend text logs.
    """

    def __init__(self):
        super().__init__("[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s")


try:
    from pythonjsonlogger import jsonlogger

    class JSONFormatter(jsonlogger.JsonFormatter):
        """
        JSON formatter for structured logs.
        """

        def __init__(self):
            super().__init__("%(asctime)s %(name)s %(levelname)s %(message)s")
except ImportError:
    import json

    class JSONFormatter(logging.Formatter):
        """
        Fallback JSON formatter if pythonjsonlogger is not installed.
        """

        def format(self, record):
            log_entry = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "name": record.name,
                "line": record.lineno,
                "message": record.getMessage(),
            }
            return json.dumps(log_entry)
