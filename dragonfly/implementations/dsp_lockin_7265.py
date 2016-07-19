from __future__ import absolute_import

from dripline.core import Endpoint, exceptions, calibrate
from .prologix import GPIBInstrument

import logging
logger = logging.getLogger(__name__)

__all__ = [
            'DSPLockin7265',
            'CallProviderMethod',
            'ProviderProperty',
          ]

class DSPLockin7265(GPIBInstrument):
    
    def __init__(self, **kwargs):
        GPIBInstrument.__init__(self, **kwargs)

    def _decode_status(self):
        status = self.send("ST")
        if not status:
            return "No response"
        data = int(status)
        if data & 0b00000010:
            status += ";invalid command"
        if data & 0b00000100:
            status += ";invalid parameter"
        return status

    def grab_data(self, key):
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
            key = key.lower()
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

class CallProviderMethod(Endpoint):
    def __init__(self, method_name, **kwargs):
        Endpoint.__init__(self, **kwargs)
        self.target_method_name = method_name

    def on_get(self):
        method = getattr(self.provider, self.target_method_name)
        return method()

    def on_set(self, value):
        method = getattr(self.provider, self.target_method_name)
        return method(value)

def status_calibration(value):
    if value[0] == 0:
        status = 'done, {} curve(s) available with {} points'.format(value[1], value[3])
    elif value[1] == 1:
        status = 'running, {} points collected'.format(value[3])
    else:
        raise ValueError('unexpected status byte value: {}'.format(value[0]))
    return status

class ProviderProperty(Endpoint):
    def __init__(self, property_key, disable_set = False, get_float = False, **kwargs):
        Endpoint.__init__(self, **kwargs)
        self.target_property = property_key
        self.disable_set = disable_set
        self.get_float = get_float

    @calibrate([status_calibration])
    def on_get(self):
        if self.get_float:
            cmd = self.target_property + "."
        else:
            cmd = self.target_property
        prop = self.provider.send(cmd)
        return prop

    def on_set(self, value):
        if self.disable_set:
            raise NameError("Set property unavailable for {}".format(self.target_property))
        if not isinstance(value, int):
            raise TypeError("Set value must be an int")
        cmd = "{} {}; {}".format(self.target_property, value, self.target_property)
        prop = self.provider.send(cmd)
        return prop
