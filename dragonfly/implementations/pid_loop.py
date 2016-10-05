'''
'''

from __future__ import print_function
__all__ = []

import datetime

import dripline
from dripline.core import Gogol, constants

import logging
logger = logging.getLogger(__name__)

__all__.append('PidController')
@dripline.core.utilities.fancy_doc
class PidController(Gogol):
    '''
    Implementation of a PID control loop with constant offset. That is, the PID equation
    is used to compute the **change** to the value of some channel and not the value
    itself. In the case of temperature control, this makes sense if the loop is working
    against some fixed load (such as a cryocooler).

    The input sensor can be anything which broadcasts regular values on the alerts
    exchange (using the standard sensor_value.<name> routing key format). Usually
    this would be a temperature sensor, but it could be anything. Similarly, the
    output is anything that can be set to a float value, though a current output
    is probably most common. After setting the new value of current, this value is checked
    to be within a range around the desired value.

    **NOTE**
    The "exchange" and "keys" arguments list below come from the Service class but
    are not valid for this class. Any value provided will be ignored
    '''

    def __init__(self,
                 input_channel,
                 output_channel,
                 check_channel,
                 payload_field='value_cal',
                 tolerance = 0.01,
                 target_value=110,
                 proportional=0.0, integral=0.0, differential=0.0,
                 maximum_out=1.0, minimum_out=1.0, delta_out_min= 0.001,
                 enable_offset_term=True,
                 minimum_elapsed_time=0,
                 **kwargs
                ):
        '''
        input_channel (str): name of the logging sensor to use as input to PID (this will override any provided values for keys)
        output_channel (str): name of the endpoint to be set() based on PID
        check_channel (str): name of the endpoint to be checked() after a set()
        input_payload_field (str): name of the field in the payload when the sensor logs (default is 'value_cal' and 'value_raw' is the only other expected value)
        target_value (float): numerical value to which the loop will try to lock the input_channel
        proportional (float): coefficient for the P term in the PID equation
        integral (float): coefficient for the I term in the PID equation
        differential (float): coefficient for the D term in the PID equation
        maximum_out (float): max value to which the output_channel may be set; if the PID equation gives a larger value this value is used instead
        delta_out_min (float): minimum value by which to change the output_channel; if the PID equation gives a smaller change, the value is left unchanged (no set is attempted)
        tolerance (float): acceptable difference between the set and get values (default: 0.01)
        '''
        kwargs.update({'keys':['sensor_value.'+input_channel]})
        Gogol.__init__(self, **kwargs)

        self._set_channel = output_channel
        self._check_channel = check_channel
        self.payload_field = payload_field
        self.tolerance = tolerance

        self.target_value = target_value

        self.Kproportional = proportional
        self.Kintegral = integral
        self.Kdifferential = differential

        self._integral= 0

        self.max_current = maximum_out
        self.min_current = minimum_out
        self.min_current_change = delta_out_min

        self.enable_offset_term = enable_offset_term
        self.minimum_elapsed_time = minimum_elapsed_time

        self._old_current = self.__get_current()
        logger.info('starting current is: {}'.format(self._old_current))

    def __get_current(self):
        request = dripline.core.RequestMessage(msgop=dripline.core.OP_GET,
                                               payload={}
                                              )
        reply = self.send_request(target=self._check_channel, request=request)
        value = reply.payload[self.payload_field]
        logger.info('old current = {}'.format(value))

        return float(value.encode('utf-8'))

    def this_consume(self, message, basic_deliver=None):
        logger.info('comsuming message')
        this_value = message.payload[self.payload_field]
        if this_value is None:
            logger.info('value is None')
            return
        self.process_new_value(timestamp=message['timestamp'], value=this_value)

    @property
    def target_value(self):
        return self._target_value
    @target_value.setter
    def target_value(self, value):
        self._target_value = value
        self._integral = 0
        self._last_data = {'delta':None,'time':datetime.datetime(1970,1,1)}

    def set_current(self, value):
        logger.info('going to set new current to: {}'.format(value))
        m = dripline.core.RequestMessage(msgop=constants.OP_SET,
                                         payload={'values':[value]},
                                        )
        logger.debug('request will be: {}'.format(m))
        reply = self.send_request(self._set_channel, m)
        logger.info('set response was: {}'.format(reply))

    def process_new_value(self, value, timestamp):
        this_time = datetime.datetime.strptime(timestamp, constants.TIME_FORMAT)

        if abs((this_time - self._last_data['time']).seconds)<self.minimum_elapsed_time:
            logger.info("not enough time has elasped: {}[{}]".format(abs((this_time - self._last_data['time']).seconds),self.minimum_elapsed_time))
            return
        logger.info('value is: {}'.format(value))
        delta = self.target_value - float(value)
        logger.info("delta is: {}".format(delta))
        #logger.info(this_time,abs((this_time - self._last_data['time']).seconds))

        self._integral += delta * (this_time - self._last_data['time']).seconds
        if (this_time - self._last_data['time']).seconds < (5 * 60) and (this_time - self._last_data['time']).seconds>0:
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
        new_current = (self._old_current or 0)*self.enable_offset_term + change_to_current

        if abs(change_to_current) < self.min_current_change:
            logger.info("current change less than min delta")
            logger.info("old[new] are: {}[{}]".format(self._old_current,new_current))
            return
        logger.info('computed new current to be: {}'.format(new_current))
        if new_current > self.max_current:
            logger.info("new current above max")
            new_current = self.max_current
        if new_current < self.min_current:
            logger.info("new current below min")
            new_current = self.min_current
        if new_current < 0.:
            logger.info("new current < 0")
            new_current = 0.

        self.set_current(new_current)
        logger.debug("checking the current value")
        current_get = self.__get_current()
        if abs(current_get-new_current) <self.tolerance:
            logger.info("current set is equal to current get")
        else:
            raise  dripline.core.DriplineValueError("set value ({}) is not equal to checked value ({})".format(new_current,current_get))

        logger.info("current set is: {}".format(new_current))
        self._old_current = new_current
