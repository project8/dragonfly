#!/usr/bin/python

'''
Utility app for doing PID control

Updated for v1.6 using async connections
'''

from __future__ import print_function

#import argparse
import datetime
import json
import os
import re
import uuid

import pika

import dripline
from dripline.core import Message, DriplineParser, constants, Service

import logging
logger = logging.getLogger('pid_loop')
logger.setLevel(logging.DEBUG)

# this probably wants to move elsewhere eventually...
class pid_controller(object):
    '''
    '''

    def __init__(self,
                 dripline_service,
                 output_channel,
                 goal=110,
                 proportional=0.0, integral=0.0, differential=0.0,
                 maximum=1.0, delta_I_min= 0.001,
                 **kwargs
                ):
        '''
        '''
        self.service = dripline_service
        self._current_channel = output_channel

        self.target_temp = goal

        self.Kproportional = proportional
        self.Kintegral = integral
        self.Kdifferential = differential

        self._integral= 0

        self.max_current = maximum
        self.min_current_change = delta_I_min

        self._old_current = self.__get_old_current()
        logger.info('starting current is: {}'.format(self._old_current))

    def __get_old_current(self):
        request = dripline.core.RequestMessage(msgop=dripline.core.OP_GET,
                                               payload={'values':{}}
                                              )
        reply = self.service.send_request(target=self._current_channel, request=request)
        value = reply.payload['value_cal']
        return float(value)

    @property
    def target_temp(self):
        return self._target_temp
    @target_temp.setter
    def target_temp(self, value):
        self._target_temp = value
        self._integral = 0
        self._last_data = {'delta':None,'time':datetime.datetime(1970,1,1)}

    def process_new_value(self, value, timestamp):
        logger.info('value is: {}'.format(value))
        delta = self.target_temp - float(value)
        logger.info("delta is: {}".format(delta))
        this_time = datetime.datetime.strptime(timestamp, constants.TIME_FORMAT)
        self._integral += delta
        if (this_time - self._last_data['time']).seconds < (5 * 60):
            derivative = (delta - self._last_data['delta']) / (this_time - self._last_data['time']).seconds
        else:
            derivative = 0.
        self._last_data = {'delta': delta, 'time': this_time}
            
        logger.info("proportional: {}".format(self.Kproportional*delta))
        logger.info("integral: {}".format(self.Kintegral*self._integral))
        logger.info("differential: {}".format(self.Kdifferential * derivative))
        change_to_current = (self.Kproportional * delta +
                             self.Kintegral * self._integral +
                             self.Kdifferential * derivative
                            )
        new_current = (self._old_current or 0) + change_to_current
        if abs(change_to_current) < self.min_current_change:
            logger.info("current change less than min delta")
            logger.info("old[new] are: {}[{}]".format(self._old_current,new_current))
            return
        logger.info('computed new current to be: {}'.format(new_current))
        if new_current > self.max_current:
            logger.info("new current above max")
            new_current = self.max_current
        if new_current < 0.:
            logger.info("new current < 0")
            new_current = 0.
        self.set_current(new_current)
        logger.info("actual set is: {}".format(new_current))
        self._old_current = new_current

    def set_current(self, value):
        logger.debug('would set new current to: {}'.format(value))
        m = dripline.core.RequestMessage(msgop=constants.OP_SET,
                                         payload={'values':[value]},
                                        )
        logger.debug('request will be: {}'.format(m))
        reply = self.service.send_request(self._current_channel, m)
        logger.info('set response was: {}'.format(reply))

class pidService(Service):
    '''
    '''
    def __init__(self, pid_args, sensor, *args, **kwargs):
        Service.__init__(self, *args, **kwargs)
        self._sensor = sensor
        self.pid = pid_controller(dripline_service=self, **pid_args)

    def on_alert_message(self, ch, method, properties, body):
        '''
        '''
        message = Message.from_encoded(body, properties.content_encoding)
        payload = message.payload

        this_sensor = None
        if '.' in method.routing_key:
            re_out = re.match(r'sensor_value.(?P<from>\S+)', method.routing_key)
            this_sensor = re_out.groupdict()['from']
        if not this_sensor == self._sensor:
            logger.info('got for another sensor: {}'.format(this_sensor))
            return
        logger.info('got a value for sensor')

        if not 'value_cal' in payload:
            logger.warning('no calibrated value')
            return
        self.pid.process_new_value(timestamp=message['timestamp'], value=payload['value_cal'])

def start_monitoring(sensor, broker='localhost', **kwargs):
    exchange = 'alerts' # this is always alerts
    keys = ['sensor_value.{}'.format(sensor)] # this is always a sensor value

    credentials = pika.PlainCredentials(**json.loads(open(os.path.expanduser('~')+'/.project8_authentications.json').read())['amqp'])

    service = pidService(pid_args=kwargs, sensor=sensor, amqp_url=broker, exchange=exchange, keys=keys)
    
    logger.info(' [*] Waiting for logs. To exit press CTRL+C')

    service.run()

if __name__ == '__main__':
    parser = DriplineParser(
                            description='Print messages from an exchange',
                            extra_logger=logger,
                            amqp_broker=True,
                            tmux_support=True,
                            twitter_support=True,
                            slack_support=True,
                           )
    parser.add_argument('-s',
                        '--sensor',
                        help='name of the temperature sensor to listen for',
                        required=True,
                       )
    parser.add_argument('-o',
                        '--output_channel',
                        help='name of the current limit to change',
                        required=True,
                       )
    parser.add_argument('-g',
                        '--goal',
                        help='set point temperature',
                        type=float,
                        required=True,
                       )
    parser.add_argument('-p',
                        '--proportional',
                        help='proportional PID term weighting',
                        default=0.0,
                        type=float,
                       )
    parser.add_argument('-i',
                        '--integral',
                        default=0.0,
                        type=float,
                        help='integral PID term weighting',
                       )
    parser.add_argument('-d',
                        '--differential',
                        default=0.0,
                        type=float,
                        help='differential PID term weighting',
                       )
    parser.add_argument('-m',
                        '--maximum',
                        default=0.0,
                        type=float,
                        help='maximum current value to set',
                       )
        
    kwargs = parser.parse_args()
    try:
        start_monitoring(**vars(kwargs))
    except KeyboardInterrupt:
        logger.info(' [*] exiting')