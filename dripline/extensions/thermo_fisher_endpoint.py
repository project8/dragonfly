from dripline.core import Entity, calibrate, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append("ThermoFisherHexGetEntity")
__all__.append("ThermoFisherNumericGetEntity")


class ThermoFisherHexGetEntity(Entity):
    '''
    A endpoint of a thermo fisher device that returns the request result as a hex-string
    '''

    def __init__(self, 
                 get_str=None,
                 **kwargs):
        '''
        Args:
            get_str: hexstring of the command, e.g. 20
        '''
        if get_str is None:
            raise ValueError('<get_str is required to __init__ ThermoFisherHexGetEntity instance')
        else:
            self.cmd_str = str(get_str).zfill(2)
        Entity.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        # setup cmd here
        to_send = [self.cmd_str]
        logger.debug(f'Send cmd in hexstr: {to_send[0]}')
        result = self.service.send_to_device(to_send)
        logger.debug(f'raw result is: {result}')

        return result

    def on_set(self, value):       
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support set")


class ThermoFisherNumericGetEntity(ThermoFisherHexGetEntity):
    '''
    A endpoint of a thermo fisher device that returns the request result as a numerica value
    '''

    units = {0: "",
             1: "degC",
             2: "degF",
             3: "L/min",
             4: "gal/min",
             5: "sec",
             6: "PSI",
             7: "bar",
             8: "MOhm cm",
             9: "%",
             10: "V",
             11: "kPa",
            }

    def __init__(self, **kwargs):
        '''
        Args:
            get_str: hexstring of the command, e.g. 20
        '''
        ThermoFisherHexGetEntity.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        # setup cmd here
        to_send = [self.cmd_str]
        logger.debug(f'Send cmd in hexstr: {to_send[0]}')
        result = self.service.send_to_device(to_send)
        logger.debug(f'raw result is: {result}')
 
        # do something here
        decimal = 10.**(-int(result[0], 16))
        unit = self.units[int(result[1], 16)]
        value = float(int(result[2:], 16))

        #result = "%f %s"%(value*decimal, unit)
        result = value*decimal
        return result

class ThermoFisherNumericEntity(ThermoFisherNumericGetEntity):
    '''
    A endpoint of a thermo fisher device that can set and get a numerical value
    '''

    def __init__(self, set_str=None, **kwargs):
        '''
        Args:
            get_str: hexstring of the get command, e.g. 20
            set_str: hexstring of the set command, e.g. B2
        '''
        if set_str is None:
            raise ValueError('<set_str is required to __init__ ThermoFisherNumericEntity instance')
        else:
            self.set_str = str(set_str).zfill(2)
        ThermoFisherNumericGetEntity.__init__(self, **kwargs)

    def on_set(self, value):
        # we need to get the decimal prefactor from a read command
        result = self.service.send_to_device([self.cmd_str])
        decimal = 10.**(-int(result[0], 16))
        unit = self.units[int(result[1], 16)]

        data = hex(round(value/decimal))[2:].zfill(4)
        result = self.service.send_to_device([self.set_str + data_str])

        # the device returns the read value after a set command
        decimal = 10.**(-int(result[0], 16))
        unit = self.units[int(result[1], 16)]
        value = float(int(result[2:], 16))

        #result = "%f %s"%(value*decimal, unit)
        result = value*decimal
        return result
