#!/usr/bin/python
'''
Utility app for monitoring the disk usages of computers
'''

from __future__ import absolute_import

import json
import os
import re
from datetime import datetime, timedelta

import dripline
from dripline.core import Gogol

import logging
logger=logging.getLogger(__name__)

class DiskMonitor(Gogol):
    '''
    A generic service that will receive AMQP alerts and make sure the disk is not full.
    '''
    def __init__(self,
                 disk_space_alert = 0.8,
                 disk_space_set_condition = 0.9,
                 time_between_warnings = 60,
                 **kwargs):
        '''
        disk_space_alert: used space threshold above which the Disk Monitor will start to send alerts
        '''
        # listen to status_message alerts channel
        kwargs.update({'exchange':'alerts','keys':['disk_status.#.#']})
        Gogol.__init__(self, **kwargs)
        self.history = {}
        self._time_between_warnings = time_between_warnings
        self._disk_space_alert = disk_space_alert
        self._disk_space_set_condition = disk_space_set_condition


    def on_alert_message(self, channel, method, properties, message):
        # parse the routing key
        logger.debug('parsing routing key')
        key_parser = r'disk_status.(?P<computername>[\w]+)'
        routing_info = re.search(key_parser, method.routing_key).groupdict()
        # parse the message
        msg = dripline.core.Message.from_encoded(message, properties.content_encoding)

        computername = routing_info['computername']
        disk = msg.payload["directory"]
        usedspace = msg.payload["used"]
        usedspacepourcent = usedspace/msg.payload["all"]

        self._update_history(computername,disk)

        if usedspacepourcent < self._disk_space_alert:
            logger.info("{}:{} -> Enough free space ({}%); doing nothing".format(computername,disk,100-int(usedspacepourcent*100),int(self._disk_space_alert*100)))
            return
        if usedspacepourcent > self._disk_space_alert and usedspacepourcent < self._disk_space_set_condition:
            if self._can_talk(computername,disk):
                # change here to critical for sending an alert on Slack
                logger.critical("{}:{} -> Free space below threshold ({}%); need to monitor!".format(computername,disk,100-int(usedspacepourcent*100)))
                self.history[computername].update({'last_alert': datetime.now() })
            else:
                logger.info("{}:{} -> Free space below threshold ({}%); need to monitor!".format(computername,disk,100-int(usedspacepourcent*100)))
        if usedspacepourcent > self._disk_space_set_condition:
            # change here to critical for sending an alert on Slack
            logger.critical("{}:{} -> Free space below critical ({}%); setting condition X!".format(computername,disk,100-int(usedspacepourcent*100)))
            # Add here the set condition thing (broadcast?)

    def _update_history(self,computername,disk):
        logger.debug('updating history')
        if computername not in self.history:
            self.history.update({computername:{}})
            # self.history[computername].update({'last_alert': None })
        if disk not in self.history[computername]:
            self.history[computername].update({disk:{}})
            self.history[computername][disk].update({'last_alert': None })

    def _can_talk(self,computername,disk):
        now = datetime.now()
        if self.history[computername][disk]['last_alert'] is None:
            return True
        deltat = now - self.history[computername][disk]['last_alert']
        if deltat.seconds > self._time_between_warnings:
            return True
        else:
            return False
