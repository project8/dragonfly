'''
Spammer of Alerts
'''

from __future__ import absolute_import

import logging
logger=logging.getLogger(__name__)

from dripline.core import Endpoint, Service, fancy_doc

from time import sleep

__all__ = []
__all__.append('AlertSpammer')

@fancy_doc
class AlertSpammer(Endpoint):
    '''
    Spammer of alerts to alerts exchange
    '''
    def __init__(self,broker=None,sleep_time = 10,*args, **kwargs):
        '''
        broker (str): the AMQP url to connect with
        sleep_time (int): seconds to sleep between alerts
        '''

        Endpoint.__init__(self,**kwargs)

        # setting the interface
        self.connection_to_alert = Service(broker=broker, exchange='alerts',keys='status_message.p8_alerts.dripline')

        #sending a welcome message
        self.level = 'warning'
        self.username = self.name
        self.sleep_time = sleep_time

    def spam(self):
        '''
        sends alerts to alerts exchange at regular time intervals
        '''
        while (True):

            severity = 'status_message.{}.{}'.format(self.level,self.username)
            logger.info('sending to alerts exchange with severity {} message ({})'.format(severity,'Redundant informations'))
            self.connection_to_alert.send_alert(severity=severity,alert='Redundant informations')
            logger.critical('I am critical')
            sleep(self.sleep_time)

    def _set_condition(self,number):
        print('set_condition {}'.format(number))
        return 'set condition {}'.format(number)
