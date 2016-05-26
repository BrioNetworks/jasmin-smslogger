# -*- coding: utf-8 -*-
import redis as r
from redis.exceptions import ConnectionError

from smslogger import settings


class RedisConnection(object):
    def __init__(self):
        self.conn = r.Redis(**settings.REDIS)

    @property
    def connection(self):
        try:
            self.conn.ping()
            return self.conn
        except ConnectionError:
            return self.connection

redis = RedisConnection()

