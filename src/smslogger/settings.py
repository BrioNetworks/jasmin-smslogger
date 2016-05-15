# -*- coding: utf-8 -*-
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static/')

ID = 1

USE_JASMIN = False

BUFFER_SIZE = 10000
TTL_SUBMITS = 120.0
INTERVAL_ASK_DEAD_SUBMITS = 100.0

AMQP_CONNECTION = {
    'host': 'smsto.ru',
    'port': 4002,
    'vhost': 't1',
    'user': 'test',
    'password': 'test1234'
}
# if USE_JASMIN, you can set '/etc/jasmin/resource/amqp0-9-1.xml'
AMQP_SPECIFICATION = os.path.join(STATIC_DIR, 'amqp0-9-1.stripped.xml')

POSTGRES = {'dbname': 'storagesms', 'user': 'postgres', 'host': 'localhost', 'port': 5432, 'password': 'root'}

REDIS = {'host': 'localhost', 'port': 6379, 'db': 0}

FORMAT_TIMES = ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', )
LOGGING_PATH = os.path.join(BASE_DIR, '../../smslogger.log')
LOGGING_FORMAT = '[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s'
LOGGING_LEVEL = logging.INFO
