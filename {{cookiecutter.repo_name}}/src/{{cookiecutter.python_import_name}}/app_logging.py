"""Setup logging for this python application."""

import logging
import sys
from enum import Enum

import coloredlogs


class LogLevel(Enum):
    """Loglevel enum."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR

    @staticmethod
    def parse(value: str) -> "LogLevel":
        """
        Parses a given string for LogLevel's.

        Parameters
        ----------
        value : str
                user provided string containing the requested log level

        Returns
        -------
        LogLevel
            Loglevel for this logger
        """
        lowered = value.lower()

        if lowered == "debug":
            result = LogLevel.DEBUG
        elif lowered == "info":
            result = LogLevel.INFO
        elif lowered in ["warning", "warn"]:
            result = LogLevel.WARNING
        elif lowered in ["err", "error"]:
            result = LogLevel.ERROR
        else:
            raise ValueError(f"Value {value} is not a valid log level.")

        return result


LOG_LEVEL: LogLevel | None = None


def setup_logging(log_level: LogLevel, colors: bool = True) -> None:
    """
    Initializes logging.

    Parameters
    ----------
    log_level : LogLevel
        The LogLevel for this logger.
    """
    global LOG_LEVEL
    root_logger = logging.getLogger()
    root_logger.info("Will use log level:", str(log_level))
    root_logger.setLevel(log_level.value)
    LOG_LEVEL = log_level
    if colors:
        coloredlogs.install(log_level.value, logger=root_logger)
    else:
        log_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(threadName)s][%(filename)s:%(lineno)d][%(levelname)s]: %(message)s"
        )
        log_handler.setFormatter(formatter)
        root_logger.addHandler(log_handler)
    pass
