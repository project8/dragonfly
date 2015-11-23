#!/usr/bin/python

'''
Utility program for monitoring the web interface and tweeting if nothing updates
'''

from __future__ import print_function
__all__ = []

# standard libs
import datetime
import json
import time

# 3rd party libs
try:
    import requests
    __all__.append('Watchdog')
except ImportError:
    pass

import logging
logger = logging.getLogger(__name__)



class Watchdog(object):
    '''
    utility for making sure some data is always showing up
    '''
    name = 'watchdog'
    def __call__(self, *args, **kwargs):
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

    def update_parser(self, parser):
        pass

#if __name__ == '__main__':
#    parser = DriplineParser(description='a simple watchdog to see if new data has shown up in the last 10 minutes',
#                            extra_logger=logger,
#                            tmux_support=True,
#                            twitter_support=True,
#                            slack_support=True,
#                           )
#    parser.parse_args()
#    monitor()
