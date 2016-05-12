import logging

import sys

from smslogger import settings


class Logger(object):
    def __init__(self):
        fmt = logging.Formatter(settings.LOGGING_FORMAT)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)

        self.logger = logging.getLogger()
        self.logger.setLevel(settings.LOGGING_LEVEL)
        self.logger.addHandler(handler)

    def getLogger(self):
        return self.logger

logger = Logger().getLogger()
