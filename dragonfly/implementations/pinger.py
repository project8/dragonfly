'''
Ping on a regular basis a list of endpoints
'''

from __future__ import absolute_import

import datetime

import logging
logger=logging.getLogger(__name__)

from dripline.core import Endpoint, Scheduler, constants, exceptions, fancy_doc

__all__ = []
__all__.append('Pinger')
@fancy_doc
class Pinger(Endpoint,Scheduler):
    '''
    Ping on a regular basis a list of service.
    It sends a request to target.ping, if a response is not given within the timeout,
    it reports a logger.critical, which sends an alert to status_message.critical.<service_name>
    via the AMQPHandler.
    services_to_ping: list of the services to ping
    ping_timeout: duration before considering a ping failed
    '''
    def __init__(self,
                 services_to_ping = [],
                 ping_timeout = 10,
                 **kwargs):

        Endpoint.__init__(self,**kwargs)
        Scheduler.__init__(self, **kwargs)

        self.services_to_ping = services_to_ping
        self.ping_timeout = ping_timeout
        self.silenced_pingers = {}

    def scheduled_action(self):
        '''
        Override Scheduler method with Pinger-specific action
        '''
        message = ""
        for item in self.services_to_ping:
            if item in self.silenced_pingers:
                if self.silenced_pingers[item] > datetime.datetime.utcnow():
                    logger.debug("skipping ping of {} until {}".format(item, self.silenced_pingers[item]))
                    continue
                else:
                    logger.debug("reactivating pinger of {}".format(item))
                    self.silenced_pingers.pop(item, None)
            logger.debug("pinging {}".format(item))
            try:
                result = self.provider.cmd(target=item, method_name="ping", value=[], timeout=self.ping_timeout)
                if result:
                    logger.info("{} is responding".format(item))
            except Exception as err:
                logger.info("Exception: {}".format(err))
                message = message + "{}\n".format(item)
        if message != "":
            logger.critical("The following services are not responding:\n{}".format(message))

    def silence_ping(self, service, endtime):
        if service not in self.services_to_ping:
            raise exceptions.DriplineValueError("Invalid service <{}>, not found in {}".format(service, self.services_to_ping))
        enddatetime = datetime.datetime.strptime(endtime,constants.TIME_FORMAT)
        if enddatetime < datetime.datetime.utcnow():
            self.silenced_pingers.pop(service, None)
            return "Ignoring endtime in the past.  Pinger active!"
        if enddatetime > datetime.datetime.utcnow()+datetime.timedelta(1):
            raise exceptions.DriplineValueError("Invalid endtime provided <{}>, one day maximum silence interval".format(endtime))
        self.silenced_pingers.update( { service : enddatetime } )
        logger.warning('Silencing pinger for {} until {}'.format(service, endtime))
