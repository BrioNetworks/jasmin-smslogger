# -*- coding: utf-8 -*-
import redis as r
from redis.exceptions import ConnectionError

from smslogger import settings
from smslogger.app_logger import logger


class RedisConnection(object):
    def __init__(self):
        self.conn = r.Redis(**settings.REDIS)

    @property
    def connection(self):
        try:
            self.conn.ping()
            return self.conn
        except ConnectionError:
            logger.warning("Redis lost connection")
            return self.connection
        except RuntimeError:
            logger.error("Fail in restoring redis connection")
            return None

redis = RedisConnection()
