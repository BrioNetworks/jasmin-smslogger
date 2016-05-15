import StringIO
import datetime
from threading import Thread, Event

import redis
from psycopg2 import DatabaseError
from psycopg2.pool import ThreadedConnectionPool

from smslogger import settings, queries
from smslogger.app_logger import logger


class BufferManager(object):

    def __init__(self):
        self._pg = PostgresManager()
        self._redis = RedisManager()

        self.buffer_size = settings.BUFFER_SIZE

        self._stop = Event()
        t = LoopingCall(self._stop, self.task_ttl_submit, settings.INTERVAL_ASK_DEAD_SUBMITS)
        t.start()

    def task_ttl_submit(self):
        logger.info("Call task find dead submits")

        columns, data, message_keys = [], [], []

        submits = self._redis.get_submits()
        for message_id, message in submits.items():
            submit = eval(message)

            if not columns:
                columns = [key for key in submit]

            time_live = datetime.datetime.now() - submit['submit_time']

            if time_live.total_seconds() >= settings.TTL_SUBMITS:
                data.append(
                    [submit[column] for column in columns]
                )

                message_keys.append(message_id)

        if columns and data:
            logger.info("Write dead submits")
            self._pg.write_buffer(data, columns)
            self._redis.clean_submits(message_keys)

    def submit(self, message_id, fields):
        self._redis.submit(message_id, fields)

    def submit_resp(self, message_id):
        self._redis.submit_resp(message_id)

    def delivery(self, message_id):
        self._redis.delivery(message_id)

        if self._redis.get_deliveries_len() >= self.buffer_size:
            logger.info("Write deliveries")
            self._write_buffer()

    def get_operator(self, key_find):
        return self._pg.get_operator(key_find)

    def get_source(self, key_find):
        return self._pg.get_source(key_find)

    def _write_buffer(self):
        columns, data = [], []

        deliveries = self._redis.get_deliveries()
        for message_id, message in deliveries.items():
            delivery = eval(message)

            if not columns:
                columns = [key for key in delivery]

            data.append(
                [delivery[column] for column in columns]
            )
        if columns and data:
            self._pg.write_buffer(data, columns)
            self._redis.clean_deliveries()

    def close(self):
        self._pg.close()
        self._stop.set()


class RedisManager(object):
    def __init__(self):
        self.connection = redis.Redis(**settings.REDIS)
        self.submit_hash_name = 'buffer:%s:submit' % (settings.ID, )
        self.delivery_hash_name = 'buffer:%s:delivery' % (settings.ID, )

    def submit(self, message_id, fields):
        self.connection.hset(self.submit_hash_name, message_id, str(fields))

    def submit_resp(self, message_id):
        message = self.update_message(message_id, 'submit_response_time')
        if message:
            self.connection.hset(self.submit_hash_name, message_id, message)

    def delivery(self, message_id):
        message = self.update_message(message_id, 'delivery_time')
        if message:
            self.connection.hset(self.delivery_hash_name, message_id, message)
            self.connection.hdel(self.submit_hash_name, message_id)

    def update_message(self, message_id, key):
        message = ''
        data = self.connection.hget(self.submit_hash_name, message_id)
        if data:
            fields = eval(data)
            if key not in fields:
                raise ValueError('Invalid data in redis hash %s' % (data,))
            fields[key] = datetime.datetime.now()
            message = str(fields)
        return message

    def get_deliveries_len(self):
        return self.connection.hlen(self.delivery_hash_name)

    def get_deliveries(self):
        return self.connection.hgetall(self.delivery_hash_name)

    def get_submits(self):
        return self.connection.hgetall(self.submit_hash_name)

    def clean_deliveries(self):
        new_key = 'gc:hashes:%s' % (self.connection.incr('gc:index'), )
        self.connection.rename(self.delivery_hash_name, new_key)
        cursor = 0
        while True:
            cursor, hash_keys = self.connection.hscan(new_key, cursor, count=100)
            if len(hash_keys) > 0:
                self.connection.hdel(new_key, *hash_keys.keys())
            if cursor == 0:
                break

    def clean_submits(self, message_keys):
        self.connection.hdel(self.submit_hash_name, *message_keys)


def long_live_connection(func):
    def wrapper(cls, *args, **kwargs):
        try:
            connection = cls.pool.getconn()
            cursor = connection.cursor()
            cursor.execute('SELECT 0')
            cursor.close()
            cls.pool.putconn(connection)
        except DatabaseError:
            cls.pool = cls.get_pool()
        return func(cls, *args, **kwargs)
    return wrapper


class PostgresManager(object):

    def __init__(self):
        self.pool = self.get_pool()

        self.operators = {}
        self.sources = {}

        self._load_references()

    @staticmethod
    def get_pool():
        return ThreadedConnectionPool(1, 5, **settings.POSTGRES)

    def _load_references(self):
        connection = self.pool.getconn()
        cursor = connection.cursor()
        self._load_operator(cursor)
        self._load_sources(cursor)
        cursor.close()
        self.pool.putconn(connection)

    def _load_sources(self, cursor):
        cursor.execute(queries.SELECT_SOURCES)
        for row in cursor:
            self.sources[row[1]] = row[0]

    def _load_operator(self, cursor):
        cursor.execute(queries.SELECT_OPERATORS)
        for row in cursor:
            self.operators[row[1]] = row[0]

    def get_operator(self, key_find):
        if key_find in self.operators:
            return self.operators[key_find]
        elif None in self.operators:
            return self.operators[None]
        else:
            raise ValueError('Not find default operator')

    @long_live_connection
    def get_source(self, key_find):
        if key_find in self.sources:
            return self.sources[key_find]
        else:
            connection = self.pool.getconn()
            cursor = connection.cursor()

            cursor.execute(queries.SELECT_OR_INSERT_SOURCE, (key_find, key_find, key_find, ))
            source = cursor.fetchone()
            connection.commit()
            cursor.close()
            self.pool.putconn(connection)

            self.sources[key_find] = source[0]
            return self.sources[key_find]

    @long_live_connection
    def write_buffer(self, data, columns):
        f = self._get_buffer(data)
        connection = self.pool.getconn()
        cursor = connection.cursor()
        cursor.copy_from(f, 'public.sms_sms', columns=columns, null="")
        connection.commit()
        self.pool.putconn(connection)

    def close(self):
        self.pool.closeall()

    @staticmethod
    def _get_buffer(data):
        stdin = '\n'.join(
            ['\t'.join(['' if field is None else '%s' % (field,) for field in message]) for message in data]) + '\n'
        return StringIO.StringIO(stdin)


class LoopingCall(Thread):
    def __init__(self, event, func, interval, *args, **kwargs):
        Thread.__init__(self)
        self.stopped = event
        self.func = func
        self.interval = interval
        self.args = args
        self.kwargs = kwargs

    def run(self):
        while not self.stopped.wait(self.interval):
            self.func(*self.args, **self.kwargs)
