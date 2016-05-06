import logging
from logging.handlers import RotatingFileHandler
from smslogger import settings


class Logger(object):
    def __init__(self):
        fmt = logging.Formatter(settings.LOGGING_FORMAT)

        handler = RotatingFileHandler(settings.LOGGING_PATH, maxBytes=10 * 1024 * 1024, backupCount=5)
        handler.setFormatter(fmt)

        self.logger = logging.getLogger()
        self.logger.setLevel(settings.LOGGING_LEVEL)
        self.logger.addHandler(handler)

    def getLogger(self):
        return self.logger

logger = Logger().getLogger()
