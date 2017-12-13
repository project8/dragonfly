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

        self.pinger_dict = { x : { 'status' : 'active' } for x in services_to_ping }
        self.ping_timeout = ping_timeout

    @property
    def ping_status(self):
        formatted = { 'value_raw' : {},
                      'value_cal' : '' }
        for service, value in self.pinger_dict.iteritems():
            single = value.copy()
            if 'timestamp' in single:
                single['timestamp'] = single['timestamp'].strftime(constants.TIME_FORMAT)
            else:
                single['timestamp'] = None
            formatted['value_raw'].update( { service : single } )
            formatted['value_cal'] += "{}\t{}\n".format(service, single)
        return formatted

    def scheduled_action(self):
        '''
        Override Scheduler method with Pinger-specific action
        '''
        message = ""
        for service in self.pinger_dict:
            if self.pinger_dict[service]['status'] == 'silenced':
                if self.pinger_dict[service]['timestamp'] > datetime.datetime.utcnow():
                    logger.debug("skipping ping of {} until {}".format(service, self.pinger_dict[service]['timestamp']))
                    continue
                else:
                    logger.debug("reactivating pinger of {}".format(service))
                    self.pinger_dict[service] = { 'status' : 'active' }
            logger.debug("pinging {}".format(service))
            try:
                result = self.provider.cmd(target=service, method_name="ping", value=[], timeout=self.ping_timeout)
                logger.info("{} is responding".format(service))
                self.pinger_dict[service]['timestamp'] = datetime.datetime.utcnow()
            except Exception as err:
                logger.info("Exception: {}".format(err))
                message = message + "{}\n".format(service)
        if message != "":
            logger.critical("The following services are not responding:\n{}".format(message))

    def silence_ping(self, service, endtime):
        if service not in self.pinger_dict:
            raise exceptions.DriplineValueError("Invalid service <{}>, not found in {}".format(service, self.pinger_dict.keys()))
        enddatetime = datetime.datetime.strptime(endtime,constants.TIME_FORMAT)
        if enddatetime < datetime.datetime.utcnow():
            self.pinger_dict[service] = { 'status' : 'active' }
            return "Ignoring endtime in the past.  Pinger active!"
        if enddatetime > datetime.datetime.utcnow()+datetime.timedelta(1):
            raise exceptions.DriplineValueError("Invalid endtime provided <{}>, one day maximum silence interval".format(endtime))
        self.pinger_dict[service] = { 'status' : 'silenced',
                                      'timestamp' : enddatetime }
        logger.warning('Silencing pinger for {} until {}'.format(service, endtime))
