#!/usr/bin/python

'''
Utility program for monitoring the web interface and tweeting if nothing updates
'''

from __future__ import print_function

# standard libs
import datetime
import json
import time

# 3rd party libs
import requests

# project 8 libs
from dripline.core import DriplineParser

import logging
logger = logging.getLogger('pid_loop')
logger.setLevel(logging.DEBUG)


def monitor():
    postgres_url = 'http://portal.project8.org/php/get_sensor_data.php'
    while True:
        start = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).isoformat()
        stop = (datetime.datetime.utcnow()).isoformat()
        response = requests.post(postgres_url, params={'start_time':start,
                                                       'stop_time':stop,
                                                      }
                                )
        if not len(json.loads(response.text)):
            logger.critical('no values logged in the last 10 minutes')
            time.sleep(60*60) # we've tweeted here so sleep for an hour
            continue
        logger.info('everything okay until: {}'.format(stop))
        time.sleep(10*60) # seems seem okay, check again in 10 minutes

if __name__ == '__main__':
    parser = DriplineParser(description='a simple watchdog to see if new data has shown up in the last 10 minutes',
                            extra_logger=logger,
                            tmux_support=True,
                            twitter_support=True,
                            slack_support=True,
                           )
    parser.parse_args()
    monitor()
