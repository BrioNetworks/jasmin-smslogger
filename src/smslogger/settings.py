# -*- coding: utf-8 -*-
import logging
import os
from os.path import join, expanduser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static/')

ID = 1

USE_JASMIN = False

BUFFER_SIZE = 100
TTL_SUBMITS = 10.0
INTERVAL_ASK_DEAD_SUBMITS = 1.0

AMQP_CONNECTION = {
    'host': '127.0.0.1',
    'port': 5672,
    'vhost': '/',
    'user': 'guest',
    'password': 'guest'
}
# if USE_JASMIN, you can set '/etc/jasmin/resource/amqp0-9-1.xml'
AMQP_SPECIFICATION = os.path.join(STATIC_DIR, 'amqp0-9-1.stripped.xml')

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
    'db': 10
}

# LOGGING_PATH = os.path.join(BASE_DIR, '../../smslogger.log')
LOGGING_FORMAT = '[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s'
LOGGING_LEVEL = logging.INFO


# Override settings on config/settings.py
# SETTINGS_OVERRIDES = join(expanduser('~'), '.config/smslogger/settings.py')

# if SETTINGS_OVERRIDES is not None and os.path.exists(SETTINGS_OVERRIDES):
#    exec open(SETTINGS_OVERRIDES) in locals()
