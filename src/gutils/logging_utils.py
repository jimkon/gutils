import atexit
import logging.config
import logging.handlers
import pathlib
import datetime as dt
import json
import logging
from typing import override

# mCoding's implementation of logging
# https://www.youtube.com/watch?v=9L77QExPmI0&ab_channel=mCoding


_logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z"
        },
        "json": {
            "()": "mylogger.MyJSONFormatter",
            "fmt_keys": {
                "level": "levelname",
                "message": "message",
                "timestamp": "timestamp",
                "logger": "name",
                "module": "module",
                "function": "funcName",
                "line": "lineno",
                "thread_name": "threadName"
            }
        }
    },
    "handlers": {
        "stderr": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "simple",
            "stream": "ext://sys.stderr"
        },
        "file_json": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "logs/logs.jsonl",
            "maxBytes": 10_000_000,
            "backupCount": 3
        },
        "queue_handler": {
            "class": "logging.handlers.QueueHandler",
            "handlers": [
                "stderr",
                "file_json"
            ],
            "respect_handler_level": True
        }
    },
    "loggers": {
        "root": {
            "level": "DEBUG",
            "handlers": [
                "queue_handler"
            ]
        }
    }
}

LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class MyJSONFormatter(logging.Formatter):
    def __init__(
            self,
            *,
            fmt_keys: dict[str, str] | None = None,
    ):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


class NonErrorFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        return record.levelno <= logging.INFO


def setup_logging(config=None):
    """
    Used to set up logging configuration, at each file. Then make a logger object like:

    logger = logging.getLogger("my_app")  # __name__ is a common choice, or one logger name per system (not per module)


    :param config:
    :return:
    """
    if config is None:
        config = _logging_config

    if isinstance(config, dict):
        logging.config.dictConfig(config)
    elif isinstance(config, str):
        config_file = pathlib.Path(config)
        with open(config_file) as f_in:
            config = json.load(f_in)
        logging.config.dictConfig(config)
    else:
        raise ValueError(f"config must be a dict, a string or a pathlib.Path, not {type(config)}")

    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)
