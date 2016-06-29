from __future__ import absolute_import

from dripline.core import Endpoint, exceptions
from .prologix import GPIBInstrument

import logging
logger = logging.getLogger(__name__)

__all__ = [
            'DSPLockin7265',
            'RawSendEndpoint',
            'CallProviderMethod',
            'ProviderProperty',
          ]

class DSPLockin7265(GPIBInstrument):
    
    def __init__(self, **kwargs):
        GPIBInstrument.__init__(self, **kwargs)
        self._device_status_cmd = "ST"

    def _confirm_setup(self):
        # set the external ADC trigger mode
        value = self.send("TADC 0;TADC")
        logger.info('trig: {}'.format(value))
        if int(value) != 0:
            raise ValueError("Failure to set TADC")
        # select the curves to sample
        value = self.send("CBD 55;CBD")
        logger.info('curve buffer: {}'.format(value))
        if int(value) != 55:
            raise ValueError("Failure to set CBD")
        # set the status byte to include all options
        value = self.send("MSK 255;MSK")
        logger.info('status mask: {}'.format(value))
        if int(value) != 255:
            raise ValueError("Failure to set MSK")
        return "done"

    def _check_status(self):
        status = self.send("ST")
        if not status:
            return "No response"
        data = int(status)
        if data & 0b00000010:
            status += ";invalid command"
        if data & 0b00000100:
            status += ";invalid parameter"
        return status

    def _grab_data(self, key):
        pts = int(self.send("LEN"))
        logger.info("expect {} pt data curves".format(pts))
        cbd = int(self.send("CBD"))
        logger.info("mask of available data curves is {}".format(cbd))
        if not cbd & 0b00010000:
            raise ValueError("No floating point data available, reconfigure CBD")
        status = self.send("M")
        status = map(int, status.split(','))
        logger.info("{} curve(s) available, {} points per curve".format(status[1], status[3]))
        if status[1] != 1:
            raise ValueError("No curve available")
        if status[3] != pts:
            raise ValueError("Unexpected number of data points")
        if not isinstance(key, int):
            if key == "x": key = 0
            elif key == "y": key = 1
            elif key == "mag": key = 2
            elif key == "phase": key = 3
            elif key == "adc": key = 5
            else:
                raise ValueError("Invalid string key.")
        if not (1<<key) & cbd:
            raise ValueError("Curve {} not available, reconfigure CBD".format(key))
        command = "DC. {}".format(key)
        extended = [command] + (pts-1)*[""]
        result = self.send(extended)
        if len(result.split(';')) != pts:
            raise ValueError("Missing data points")
        return result

    def _taking_data_status(self):
        result = self.send("M")
        curve_status = result.split(',')[0]
        status  = None
        if curve_status == '0':
            status = 'done'
        elif curve_status == '1':
            status = 'running'
        else:
            logger.error("unexpected status byte: {}".format(curve_status))
            raise ValueError('unexpected status byte value')
        return status

    @property
    def number_of_points(self):
        return self.send("LEN")
    @number_of_points.setter
    def number_of_points(self, value):
        if not isinstance(value, int):
            raise TypeError('value must be an int')
        status = self.send("LEN {};LEN".format(value))
        if not int(status) == value:
            raise ValueError("Failure to set number_of_points")

    @property
    def sampling_interval(self):
        '''
        Returns the sampling interval in ms
        '''
        return self.send("STR")
    @sampling_interval.setter
    def sampling_interval(self, value):
        '''
        set the sampling interval in integer ms (must be a multiple of 5)
        '''
        if not isinstance(value, int):
            raise TypeError('value must be an int')
        status = self.send("STR {};STR".format(value))
        if not int(status) == value:
            raise ValueError("Failure to set sampling_interval")

class RawSendEndpoint(Endpoint):

    def __init__(self, base_str, **kwargs):
        Endpoint.__init__(self, **kwargs)
        self.base_str = base_str

    def on_get(self):
        return self.provider.send(self.base_str)
    
    def on_set(self, value):
        return self.provider.send(self.base_str + " " + value)

class CallProviderMethod(Endpoint):
    def __init__(self, method_name, **kwargs):
        Endpoint.__init__(self, **kwargs)
        self.target_method_name = method_name

    def on_get(self):
        method = getattr(self.provider, self.target_method_name)
        logger.debug('method is: {}'.format(method))
        return method()

    def on_set(self, value):
        method = getattr(self.provider, self.target_method_name)
        return method(value)

class ProviderProperty(Endpoint):
    def __init__(self, property_name, **kwargs):
        Endpoint.__init__(self, **kwargs)
        self.target_property = property_name

    def on_get(self):
        prop = getattr(self.provider, self.target_property)
        return prop

    def on_set(self, value):
        if hasattr(self.provider, self.target_property):
            setattr(self.provider, self.target_property, value)
        else:
            raise AttributeError
        return 'done'
