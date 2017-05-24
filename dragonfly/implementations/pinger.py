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

class Pinger(Endpoint,Scheduler):
    '''
    Ping on a regular basis a list of service.
    It sends a request to target.ping, if a response is not given within the timeout,
    it reports a logger.critical, which sends a alert to status_message.critical.<service_name>
    via the AMQPHandler.
    services_to_ping: list of the services to ping
    ping_timeout: duration before considering a ping failed
    '''
    def __init__(self,
                 broker=None,
                 services_to_ping = [],
                 ping_timeout = 10,
                 *args, **kwargs):

        Endpoint.__init__(self,**kwargs)
        Scheduler.__init__(self, **kwargs)

        self.services_to_ping = services_to_ping
        self.ping_timeout = ping_timeout

    # FIXME: the following method is called by Scheduler on a regular basis.
    # Should be replaced with a more generic method name.
    def _log_a_value(self):
        message = ""
        for item in self.services_to_ping:
            logger.info("pinging {}".format(item))
            try:
                result = self.provider.cmd(target=str(item), method_name="ping", value=[], timeout=self.ping_timeout)
                if result:
                    logger.info("{} is responding".format(item))
            except Exception as err:
                logger.info(err)
                message = message + "{}\n".format(item)
        if message != "":
            logger.critical("The following services are not responding:\n{}".format(message))

        # start to sleep before restarting
        self._timeout_handle = self.service._connection.add_timeout(self._log_interval, self._log_a_value)
