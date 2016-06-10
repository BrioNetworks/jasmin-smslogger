#!/usr/bin/env python
from setuptools import setup, find_packages
from os.path import expanduser, join

import os
import sys
sys.path.insert(0, 'src')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = join(expanduser('~'), '.config/smslogger')

requires = [
    'Twisted>=16.1.1',
    'txAMQP>=0.6.2',
    'enum>=0.4.6',
    'smpp.pdu>=0.3',
    'psycopg2>=2.6.1',
    'redis',
]

setup(
    name='smslogger',
    version='develop',
    keywords='',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    url='https://github.com/dmtmalin/jasmin-smslogger',
    license='',
    author='dmt',
    author_email='',
    description='',
    zip_safe=False,
    include_package_data=True,
    install_requires=requires,
    entry_points={
        'console_scripts': [
            'smslogger = smslogger.manage:main',
        ]
    },
    data_files=[
        (CONFIG_PATH, [os.path.join(BASE_DIR, 'config/settings.py')])
    ]
)
