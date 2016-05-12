import StringIO
import datetime
import psycopg2
import redis

from smslogger import settings


class BufferManager(object):

    def __init__(self):
        self.pg = PostgresManager()
        self.redis = RedisManager()

        self.buffer_size = settings.BUFFER_SIZE

    def submit(self, *args, **kwargs):
        self.redis.submit(*args, **kwargs)

        if self.redis.get_hash_len('delivery') >= self.buffer_size:
            self._write_buffer()

    def submit_resp(self, *args, **kwargs):
        self.redis.submit_resp(*args, **kwargs)

    def delivery(self, *args, **kwargs):
        self.redis.delivery(*args, **kwargs)

    def get_operator(self, *args, **kwargs):
        return self.pg.get_operator(*args, **kwargs)

    def get_source(self, *args, **kwargs):
        return self.pg.get_source(*args, **kwargs)

    def _write_buffer(self):
        columns, data = [], []

        deliveries = self.redis.get_deliveries()
        for message_id, message in deliveries.items():
            fields = eval(message)

            if not columns:
                columns = [key for key in fields]

            data.append(
                [fields[column] for column in columns]
            )
        if columns and data:
            self.pg.write_buffer(data, columns)
            self.redis.clean_deliveries()


class RedisManager(object):
    def __init__(self):
        self.connection = redis.Redis(**settings.REDIS)

    def submit(self, message_id, fields):
        self.connection.hset('submit', message_id, str(fields))

    def submit_resp(self, message_id):
        message = self.update_message(message_id, 'submit_response_time')
        if message:
            self.connection.hset('submit', message_id, message)

    def delivery(self, message_id):
        message = self.update_message(message_id, 'delivery_time')
        if message:
            self.connection.hset('delivery', message_id, message)
            self.connection.hdel('submit', message_id)

    def update_message(self, message_id, key):
        message = ''
        data = self.connection.hget('submit', message_id)
        if data:
            fields = eval(data)
            if key not in fields:
                raise ValueError('Invalid data in redis hash %s' % (data,))
            fields[key] = datetime.datetime.now()
            message = str(fields)
        return message

    def get_hash_len(self, hash_name):
        return self.connection.hlen(hash_name)

    def get_deliveries(self):
        return self.connection.hgetall('delivery')

    def clean_deliveries(self):
        new_key = 'gc:hashes:%s' % (self.connection.incr('gc:index'), )
        self.connection.rename('delivery', new_key)
        cursor = 0
        while True:
            cursor, hash_keys = self.connection.hscan(new_key, cursor, count=100)
            if len(hash_keys) > 0:
                self.connection.hdel(new_key, *hash_keys.keys())
            if cursor == 0:
                break


class PostgresManager(object):

    def __init__(self):
        self.connection = psycopg2.connect(**settings.POSTGRES)

        self.operators = {}
        self.sources = {}

        self._load_references()

    def _load_references(self):
        cursor = self.connection.cursor()

        cursor.execute('SELECT id, routed_cid FROM public.sms_operator')
        for row in cursor:
            self.operators[row[1]] = row[0]

        cursor.execute('SELECT id, address FROM PUBLIC.sms_source')
        for row in cursor:
            self.sources[row[1]] = row[0]

        cursor.close()

    def get_operator(self, key_find):
        if key_find in self.operators:
            return self.operators[key_find]
        elif None in self.operators:
            return self.operators[None]
        else:
            raise ValueError('Not find default operator')

    def get_source(self, key_find):
        if key_find in self.sources:
            return self.sources[key_find]
        else:
            cursor = self.connection.cursor()
            cursor.execute('INSERT INTO public.sms_source (address) VALUES (%s) RETURNING id', (key_find,))
            source = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            return source[0]

    def write_buffer(self, data, columns):
        f = self._get_buffer(data)
        cursor = self.connection.cursor()
        cursor.copy_from(f, 'public.sms_sms', columns=columns)
        self.connection.commit()

    @staticmethod
    def _get_buffer(data):
        stdin = '\n'.join(['\t'.join(['' if value is None else '%s' % (value,) for value in item]) for item in data]) + '\n'
        return StringIO.StringIO(stdin)


def test():
    b = BufferManager()

    b.redis.connection.flushdb()

    operator = b.get_operator('bee')
    source = b.get_source('test3')

    mess_id = '9410fb2d'
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

    b.submit_resp(mess_id)
    b.delivery(mess_id)

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
