#!/usr/bin/python

'''
Utility app for printing all of the messages through some exchange
'''

from __future__ import print_function

# standard libs
import argparse
import json
import os
import sys

# 3rd party libs
import pika
import sqlalchemy

# internal imports
from dripline.core import Gogol

import logging
from dripline.core import DriplineParser
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def start_monitoring(amqp='localhost', exchange='alerts', keys=['sensor_value.#'],
                     user=None, passwd=None, sql_server=None, sql_database=None, **kwargs):
    if sql_database is None:
        sql_database = 'p8_sc_db'
    if isinstance(keys, str):
        keys=[keys]
    if keys == ['sensor_value']:
        logger.warning('You have used the older format binding_key, this will miss messages in the new format\nUse "sensor_value.#" (the new default) if you want to bind to all sensor data')
    logger.info('making connections')
    consumer = Gogol(broker_host=amqp, exchange='alerts', keys=keys)
    credentials = json.loads(open(os.path.expanduser('~')+'/.project8_authentications.json').read())['postgresql']

    engine = sqlalchemy.create_engine('postgresql://{}:{}@{}/{}'.format(credentials['username'], credentials['password'], sql_server, sql_database))
    meta = sqlalchemy.MetaData(engine)
    num_table = sqlalchemy.Table("numeric_data", meta, autoload=True)
    consumer.table = num_table

    consumer.this_consume=consumer._postgres_consume
    try:
        logger.info("starting message consumption")
        consumer.start()
    except KeyboardInterrupt as err:
        logger.info('exiting')
        sys.exit()

if __name__ == '__main__':
    parser = DriplineParser(extra_logger=logger,
                            amqp_broker=True,
                            tmux_support=True,
                            config_file=True,
                            twitter_support=True,
                            slack_support=True
                           )
    parser.add_argument('-e',
                        '--exchange',
                        help='name of the amqp exchange to monitor',
                        default='alerts',
                       )
    parser.add_argument('-k',
                        '--keys',
                        metavar='BINDING_KEYS',
                        help='amqp binding keys to follow',
                        default=['sensor_value.#'],
                        nargs='*',
                       )
#    parser.add_argument('-u',
#                        '--user',
#                        help='username on posgres',
#                       )
#    parser.add_argument('-p',
#                        '--passwd',
#                        help="user's postgres password",
#                       )
    parser.add_argument('-s',
                        '--sql_server',
                        metavar='POSTGRES_SERVER',
                        help="fully qualified network path for postgres server",
                        default='localhost',
                       )
    parser.add_argument('-d',
                        '--database',
                        dest='sql_database',
                        help="specify the name of the database to use (generally only used for specifying an alternate database for debugging)"
                       )
    kwargs = parser.parse_args()
#    kwargs = make_parser().parse_args()
#    if kwargs.passwd is not None or kwargs.user is not None:
#        logger.warning('passing username and/or password is no loger supported. You must use the authentication file ~/.project8_authentications.json')
    try:
        start_monitoring(**vars(kwargs))
    except KeyboardInterrupt:
        print(' [*] exiting')
