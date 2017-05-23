'''
Ping on a regular basis a list of endpoints
'''

from __future__ import absolute_import

import json
import os

import logging
logger=logging.getLogger(__name__)

import dripline
from dripline.core import Endpoint

from time import sleep

__all__ = []
__all__.append('Pinger')


class Pinger(Endpoint):
    '''
    Spammer of Alerts
    '''
    def __init__(self,
                 broker=None,
                 sleep_time = 10,
                 services_to_ping = [],
                 ping_timeout = 10,
                 *args, **kwargs):

        Endpoint.__init__(self,**kwargs)

        # setting the interface
        self.connection_to_alert = dripline.core.Service(broker=broker, exchange='alerts',keys='status_message.p8_alerts.dripline')

        #sending a welcome message
        self.this_channel = 'p8_alerts'
        self.username = self.name
        self.sleep_time = sleep_time
        self.services_to_ping = services_to_ping
        self.ping_timeout = ping_timeout

    def start_ping(self):
        while (True):
            print(self.services_to_ping)
            for item in self.services_to_ping:
                logger.info("pinging {}".format(item))
                try:
                    result = self.provider.cmd(target=str(item), method_name="ping", value=[], timeout=self.ping_timeout)
                    if result:
                        logger.info("{} is responding".format(item))
                except Exception as err:
                    logger.critical("{} is not responding".format(item))
            sleep(self.sleep_time)

    def emit(self, record):
        this_channel = 'p8_alerts'
        severity = 'status_message.{}.{}'.format(this_channel,self.username)
        self.connection_to_alert.send_status_message(severity=severity,alert=record.msg)
