'''
Spammer of Alerts
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
__all__.append('AlertSpammer')


class AlertSpammer(Endpoint):
    '''
    Spammer of Alerts
    '''
    def __init__(self,broker=None,sleep_time = 10,*args, **kwargs):

        Endpoint.__init__(self,**kwargs)

        # setting the interface
        self.connection_to_alert = dripline.core.Service(broker=broker, exchange='alerts',keys='status_message.p8_alerts.dripline')

        #sending a welcome message
        self.this_channel = 'p8_alerts'
        self.username = self.name
        self.sleep_time = sleep_time

    def spam(self):
        while (True):

            severity = 'status_message.{}.{}'.format(self.this_channel,self.username)
            print('sending to alerts exchange with severity {} message ({})'.format(severity,'Redundant informations'))
            self.connection_to_alert.send_status_message(severity=severity,alert='Redundant informations')
            logger.critical('I am critical')
            sleep(self.sleep_time)

    def _set_condition(self,number):
        print('set_condition {}'.format(number))
        return 'set condition {}'.format(number)
