import StringIO

import datetime
import psycopg2 as psycopg2

from smslogger.utils import utc_to_local


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

conn = psycopg2.connect("dbname = 'storagesms' user = 'postgres' host = 'smsto.ru' port=4004 password = 'pass'")

storage = BufferSms(conn, 2)

create_time = utc_to_local('2010-01-01 00:00:00')

o = storage.findOperator('bee')
s = storage.findOrSaveSource('test2')
fields = ('message-1', 'hello', 'con-1', 'routed-1', 0, 'uid-1', o, s, 'dest-1', 0, 'ok', create_time, datetime.datetime.now())

storage.writeToBuffer(fields)

fields = ('message-1', 'hello', 'con-1', 'routed-1', 0, 'uid-1', o, s, 'dest-1', 0, 'ok', create_time, datetime.datetime.now())

storage.writeToBuffer(fields)

