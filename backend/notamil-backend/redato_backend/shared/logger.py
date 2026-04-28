import logging
import sys

from google.cloud.logging import Client
from google.cloud.logging.handlers import (
    AppEngineHandler,
    CloudLoggingHandler,
    ContainerEngineHandler,
)
from redato_backend.shared.constants import ENABLE_STACKDRIVER, LOG_LEVEL, LOGGER_NAME

if ENABLE_STACKDRIVER == "True":
    log_client: Client = Client()
    log_client.setup_logging()
else:
    log_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger() -> logging.Logger:
    _logger = logging.getLogger(LOGGER_NAME)
    _logger.setLevel(LOG_LEVEL)
    _logger.handlers = [
        handler
        for handler in _logger.handlers
        if isinstance(
            handler, (CloudLoggingHandler, ContainerEngineHandler, AppEngineHandler)
        )
    ]
    return _logger


logger = get_logger()
