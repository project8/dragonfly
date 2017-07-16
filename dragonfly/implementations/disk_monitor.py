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
                 disk_space_critical = 0.9,
                 time_between_warnings = 60,
                 actions_conditions = None,
                 **kwargs):
        '''
        disk_space_alert: used space threshold above which the Disk Monitor will start to send alerts
        '''
        # listen to status_message alerts channel
        kwargs.update({'keys':['disk_status.#.#']})
        Gogol.__init__(self, **kwargs)
        self.history = {}
        self._time_between_warnings = time_between_warnings
        self._disk_space_alert = disk_space_alert
        self._disk_space_critical = disk_space_critical
        for condition in action_conditions:
            try:
                if not isinstance(condition['condition_to_set'],int):
                    condition['condition_to_set'] = int(condition['condition_to_set'])
            except ValueError:
                logger.critical('Invalid "condition_to_set" <{}> in action_condition for {}'.format(condition['condition_to_set'], condition['name']))
                condition['name'] = None
        self._action_when_critical = actions_conditions


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
        if usedspacepourcent > self._disk_space_alert and usedspacepourcent < self._disk_space_critical:
            if self._can_talk(computername,disk):
                # change here to critical for sending an alert on Slack
                logger.critical("{}:{} -> Free space below threshold ({}%); need to monitor!".format(computername,disk,100-int(usedspacepourcent*100)))
                self.history[computername][disk].update({'last_alert': datetime.now() })
            else:
                logger.info("{}:{} -> Free space below threshold ({}%); need to monitor!".format(computername,disk,100-int(usedspacepourcent*100)))
        if usedspacepourcent > self._disk_space_critical:
            # change here to critical for sending an alert on Slack
            for a_dict in self._action_when_critical:
                if computername == a_dict['name']:
                    logger.critical("{}:{} -> Free space below critical ({}%); setting condition {}!".format(computername,disk,100-int(usedspacepourcent*100),a_dict['condition_to_set']))
                    result = self.provider.cmd('broadcast','set_condition', a_dict['condition_to_set'], timeout=30)
                    logger.critical("Result of broadcast.set_condition {}: \n {}".format(a_dict['condition_to_set'],result))
                    return
            logger.critical("{}:{} -> Free space below critical ({}%); no condition defined: require manual operations!".format(computername,disk,100-int(usedspacepourcent*100)))

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
