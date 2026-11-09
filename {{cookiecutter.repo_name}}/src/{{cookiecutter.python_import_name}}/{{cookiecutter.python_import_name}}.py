"""Main python file for {{cookiecutter.project_name}}."""
from datetime import datetime, timedelta
from {{cookiecutter.python_import_name}}.app_logging import setup_logging, LogLevel
import logging
import traceback

logger = logging.getLogger(__name__)


def testable_function(input: datetime) -> datetime:
    """Testable function."""
    return input + + timedelta(hours=1)


def start_app(loglevel: str, colors: bool) -> None:
    """{{cookiecutter.project_name}} application."""
    setup_logging(LogLevel.parse(loglevel), colors)
    try:
        logger.info(f"The time + 1 hour is: {testable_function(datetime.now())}")

        # TODO insert your code here

    except Exception as error:
        logger.error(f"Error occured: {error} at: {traceback.format_exc(limit=-1)}")
        logger.debug(traceback.format_exc())


if __name__ == '__main__':
    start_app(loglevel="DEBUG", colors=True)
