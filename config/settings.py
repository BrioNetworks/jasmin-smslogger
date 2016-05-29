import logging

ID = 1

USE_JASMIN = False

BUFFER_SIZE = 1000
TTL_SUBMITS = 120.0
INTERVAL_ASK_DEAD_SUBMITS = 100.0

AMQP_CONNECTION = {
    'host': 'smsto.ru',
    'port': 4002,
    'vhost': 't1',
    'user': 'test',
    'password': 'test1234'
}

AMQP_SPECIFICATION ='/etc/jasmin/resource/amqp0-9-1.xml'

POSTGRES = {
    'dbname': 'storagesms',
    'user': 'postgres',
    'host': 'localhost',
    'port': 5432,
    'password': 'root'
}

REDIS = {
    'host': 'localhost',
    'port': 6379,
    'db': 0
}

LOGGING_FORMAT = '[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s'
LOGGING_LEVEL = logging.INFO
