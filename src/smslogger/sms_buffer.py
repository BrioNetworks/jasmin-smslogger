import StringIO

import datetime
import psycopg2
import redis

from smslogger.utils import utc_to_local
from smslogger import settings


class BufferManager(object):

    def __init__(self, buffer_size):
        self.pg = PostgresManager()
        self.redis = redis.Redis(**settings.REDIS)
        self.redis.flushdb()

        self.buffer_size = buffer_size

    def submit(self, message_id, fields):
        self.redis.hset('submit', message_id, str(fields))

    def submitResp(self, message_id):
        data = self.redis.hget('submit', message_id)
        if data:
            fields = eval(data)
            key = 'submit_response_time'
            if key not in fields:
                raise ValueError('Invalid data in redis hash %s' % (data, ))

            fields[key] = datetime.datetime.now()

            self.redis.hset('submit', message_id, str(fields))

    def delivery(self, message_id):
        data = self.redis.hget('submit', message_id)
        if data:
            fields = eval(data)
            key = 'delivery_time'
            if key not in fields:
                raise ValueError('Invalid data in redis hash %s' % (data,))

            fields[key] = datetime.datetime.now()

            self.redis.hset('delivery', message_id, str(fields))
            self.redis.hdel('submit', message_id)


    def getOperator(self, key_find):
        return self.pg.getOperator(key_find)

    def getSource(self, key_find):
        return self.pg.getSource(key_find)


class PostgresManager(object):

    def __init__(self):
        self.connection = psycopg2.connect(**settings.POSTGRES)

        self.operators = {}
        self.sources = {}

        self._loadReferences()

    def _loadReferences(self):
        cursor = self.connection.cursor()

        cursor.execute('SELECT id, routed_cid FROM public.sms_operator')
        for row in cursor:
            self.operators[row[1]] = row[0]

        cursor.execute('SELECT id, address FROM PUBLIC.sms_source')
        for row in cursor:
            self.sources[row[1]] = row[0]

        cursor.close()

    def getOperator(self, key_find):
        if key_find in self.operators:
            return self.operators[key_find]
        elif None in self.operators:
            return self.operators[None]
        else:
            raise ValueError('Not find default operator')

    def getSource(self, key_find):
        if key_find in self.sources:
            return self.sources[key_find]
        else:
            cursor = self.connection.cursor()
            cursor.execute('INSERT INTO public.sms_source (address) VALUES (%s) RETURNING id', (key_find,))
            source = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            return source[0]




class BufferSms(object):

    def __init__(self, pg_connection, buffer_size):
        self.connection = pg_connection
        self.buffer_size = buffer_size
        self.buffer = []
        self.sources = {}
        self.operators = {}

        self._loadSourcesAndOperators()

    def _loadSourcesAndOperators(self):
        cursor = self.connection.cursor()

        cursor.execute('SELECT id, routed_cid FROM public.sms_operator')
        for row in cursor:
            self.operators[row[1]] = row[0]

        cursor.execute('SELECT id, address FROM PUBLIC.sms_source')
        for row in cursor:
            self.sources[row[1]] = row[0]

        cursor.close()

    def findOperator(self, key_find):
        if key_find in self.operators:
            return self.operators[key_find]
        elif None in self.operators:
            return self.operators[None]
        else:
            raise ValueError('Not find default operator')

    def findOrSaveSource(self, key_find):
        if key_find in self.sources:
            return self.sources[key_find]
        else:
            cursor = self.connection.cursor()
            cursor.execute('INSERT INTO public.sms_source (address) VALUES (%s) RETURNING id', (key_find,))
            source = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            return source[0]

    def writeToBuffer(self, *fields):
        self.buffer.append(*fields)

        if len(self.buffer) >= self.buffer_size:
            f = self._getBuffer()
            cursor = self.connection.cursor()
            cursor.copy_from(f, 'public.sms_sms', columns=(
                'message_id', 'message', 'source_connector', 'routed_cid', 'rate', 'uid', 'operator_id', 'source_id',
                'destination', 'pdu_count', 'status', 'create_time', 'submit_time'))
            self.connection.commit()

            self.buffer = []

    def _getBuffer(self):
        stdin = '\n'.join(['\t'.join(['%s' % (value,) for value in item]) for item in self.buffer]) + '\n'
        return StringIO.StringIO(stdin)


'''
conn = psycopg2.connect(**settings.PG_CONNECTION)

storage = BufferSms(conn, 2)

create_time = utc_to_local('2010-01-01 00:00:00')

o = storage.findOperator('bee')
s = storage.findOrSaveSource('test2')
fields = ('message-1', 'hello', 'con-1', 'routed-1', 0, 'uid-1', o, s, 'dest-1', 0, 'ok', create_time, datetime.datetime.now())

storage.writeToBuffer(fields)
'''
b = BufferManager(1)

operator = b.getOperator('bee')
source = b.getSource('test3')

mess_id = '9410fb2d-2adb-4eec-bb89-132a279f8cf4'
b.submit(mess_id, {
    'message_id': mess_id,
    'message': 'hello',
    'source_connector': 'smppsapi',
    'routed_cid': 'test3',
    'rate': 0,
    'uid': None,
    'destination': '1111111111',
    'pdu_count': 1,
    'status': 'ESME_ROK',
    'create_time': datetime.datetime.now(),
    'submit_time': datetime.datetime.now(),
    'submit_response_time': None,
    'delivery_time': None,
    'operator_id': operator,
    'source_id': source
})

b.submitResp(mess_id)
b.delivery(mess_id)


