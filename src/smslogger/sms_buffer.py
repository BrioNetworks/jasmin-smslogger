# -*- coding: utf-8 -*-
import StringIO
import datetime

from threading import Thread, Event

from smslogger import settings, queries
from smslogger.app_logger import logger
from smslogger.pg_pool import pool
from redis_connection import redis


class BufferManager(object):

    def __init__(self):
        self._pg = PostgresManager()
        self._redis = RedisManager()

        self.buffer_size = settings.BUFFER_SIZE

        self._stop = Event()
        t = LoopingCall(self._stop, self._task_find_dead_submits, settings.INTERVAL_ASK_DEAD_SUBMITS)
        t.start()

    def _task_find_dead_submits(self):
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
        columns, data, message_keys = [], [], []

        deliveries = self._redis.get_deliveries()
        for message_id, message in deliveries.items():
            delivery = eval(message)

            if not columns:
                columns = [key for key in delivery]

            data.append(
                [delivery[column] for column in columns]
            )

            message_keys.append(message_id)

        if columns and data:
            is_write = self._pg.write_buffer(data, columns)
            if not is_write:
                logger.info('Try write buffer line to line')
                for item in data:
                    self._pg.write_buffer([item], columns)

            self._redis.clean_deliveries(message_keys)

    def close(self):
        pool.close()
        self._stop.set()


class RedisManager(object):
    def __init__(self):
        self.submit_hash_name = 'buffer:%s:submit' % (settings.ID, )
        self.delivery_hash_name = 'buffer:%s:delivery' % (settings.ID, )

    def submit(self, message_id, fields):
        redis.connection.hset(self.submit_hash_name, message_id, str(fields))

    def submit_resp(self, message_id):
        message = self.update_message(message_id, 'submit_response_time')
        if message:
            redis.connection.hset(self.submit_hash_name, message_id, message)

    def delivery(self, message_id):
        message = self.update_message(message_id, 'delivery_time')
        if message:
            redis.connection.hset(self.delivery_hash_name, message_id, message)
            redis.connection.hdel(self.submit_hash_name, message_id)

    def update_message(self, message_id, key):
        message = ''
        data = redis.connection.hget(self.submit_hash_name, message_id)
        if data:
            fields = eval(data)
            if key not in fields:
                raise ValueError('Redis: not find in data %s field %s' % (data, key, ))
            fields[key] = datetime.datetime.now()
            message = str(fields)
        return message

    def get_deliveries_len(self):
        return redis.connection.hlen(self.delivery_hash_name)

    def get_deliveries(self):
        return redis.connection.hgetall(self.delivery_hash_name)

    def get_submits(self):
        return redis.connection.hgetall(self.submit_hash_name)

    def clean_deliveries(self, message_keys):
        self._clean_hkeys(self.delivery_hash_name, message_keys)

    def clean_submits(self, message_keys):
        self._clean_hkeys(self.submit_hash_name, message_keys)

    @staticmethod
    def _clean_hkeys(hash_name, message_keys):
        chunks_num = 100
        chunks = [message_keys[i:i+chunks_num] for i in range(0, len(message_keys), chunks_num)]
        for chunk in chunks:
            redis.connection.hdel(hash_name, *chunk)


class PostgresManager(object):
    def __init__(self):
        self.operators = {}
        self.sources = {}

        self._load_references()

    def _load_references(self):
        with pool.db_cursor() as cursor:
            self._load_operator(cursor)
            self._load_sources(cursor)

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
        else:
            if None not in self.operators:
                with pool.db_cursor() as cursor:
                    cursor.execute(queries.INSERT_UNKNOWN_OPERATOR, (None, 'Unknown', ))
                    operator = cursor.fetchone()
                    self.operators[None] = operator[0]
            return self.operators[None]

    def get_source(self, key_find):
        if key_find not in self.sources:
            with pool.db_cursor() as cursor:
                cursor.execute(queries.SELECT_OR_INSERT_SOURCE, (key_find, key_find, key_find, ))
                source = cursor.fetchone()
                self.sources[key_find] = source[0]
        return self.sources[key_find]

    def write_buffer(self, data, columns):
        try:
            f = self._get_buffer(data)
            with pool.db_cursor() as cursor:
                cursor.copy_from(f, 'public.sms_sms', columns=columns, null='')
            return True
        except Exception as e:
            logger.error('Exception in write_buffer: %s, with data %s' % (e, data))
            return False

    @staticmethod
    def _get_buffer(data):
        stdin = '\n'.join(
            ['\t'.join(['' if field is None else ('%s' % (field,)).decode('utf-8', 'replace') for field in message])
             for message in data]) + '\n'
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
