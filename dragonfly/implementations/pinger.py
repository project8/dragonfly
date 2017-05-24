'''
Ping on a regular basis a list of endpoints
'''

from __future__ import absolute_import

import json
import os

import logging
logger=logging.getLogger(__name__)

import dripline
from dripline.core import Endpoint, Scheduler

from time import sleep

__all__ = []
__all__.append('Pinger')

class Pinger(Scheduler,Endpoint):
    '''
    Ping on a regular basis a list of service.
    It sends a request to target.ping, if a response is not given within the timeout,
    it reports a logger.critical, which sends a alert to status_message.critical.<service_name>
    via the AMQPHandler.
    '''
    def __init__(self,
                 broker=None,
                 ping_interval = 60,
                 services_to_ping = [],
                 ping_timeout = 10,
                 *args, **kwargs):


        Endpoint.__init__(self,**kwargs)

        Scheduler.__init__(self, **kwargs)
        
        self.ping_interval = ping_interval
        self.services_to_ping = services_to_ping
        self.ping_timeout = ping_timeout

        # logger.info('sleep before starting pinging the services')
        # sleep(self.ping_interval)

    def _log_a_value(self):
        message = ""
        for item in self.services_to_ping:
            logger.info("pinging {}".format(item))
            try:
                result = self.provider.cmd(target=str(item), method_name="ping", value=[], timeout=self.ping_interval)
                if result:
                    logger.info("{} is responding".format(item))
            except Exception as err:
                logger.info(err)
                message = message + "{}\n".format(item)
        if message != "":
            logger.critical("The following services are not responding:\n{}".format(message))
