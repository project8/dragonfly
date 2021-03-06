#!/usr/bin/python
'''
Script to manually log a supplied value to a named sensor
'''

from __future__ import print_function, absolute_import

import dripline

import logging
logger = logging.getLogger('manual_logger')
logger.setLevel(logging.DEBUG)


def __send_log_message(broker, sensor, value_raw, value_cal=None, extra_memo=None, **kwargs):
    # construct log info
    to_log = {'from':sensor,
              'values':{'value_raw': value_raw,
                       'memo': 'logged manually',
                      },
             }
    if value_cal is not None:
        to_log['values']['value_cal'] = value_cal
    if extra_memo is not None:
        to_log['values']['memo'] += extra_memo
    logger.debug('logging to sensor: {}'.format(sensor))
    logger.debug('with info:\n{}'.format(to_log['values']))

    # make connection
    # note that we're not consuming, so the exchange and key values here don't really matter
    conn = dripline.core.Service(amqp_url = broker,
                                 exchange = 'alerts',
                                 keys = '#'
                                )
    routing_key = 'sensor_value.{}'.format(sensor)
    conn.send_alert(severity=routing_key, alert=to_log)
    logger.info('log sent')


if __name__ == '__main__':
    parser = dripline.core.DriplineParser(extra_logger=logger,
                                          amqp_broker=True,
                                          config_file=True,
                                          twitter_support=True,
                                         )
    parser.add_argument('sensor',
                        help="name of the sensor to log",
                       )
    parser.add_argument('value_raw',
                        help="value to log",
                       )
    parser.add_argument('value_cal',
                        nargs='?',
                        default=None,
                        help="calibrated value to log",
                       )
    args = parser.parse_args()
    logger.info('args parsed, emitting the log')
    __send_log_message(**vars(args))
