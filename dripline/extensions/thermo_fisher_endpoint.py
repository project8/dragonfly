from dripline.core import Entity, calibrate, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append("ThermoFisherGetEntity")
class ThermoFisherGetEntity(Entity):
    '''
    A simple endpoint which stores a value but returns that value + a random offset
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

    def __init__(self, 
                 get_str=None,
                 **kwargs):
        '''
        Args:
        '''
        if get_str is None:
            raise ValueError('<base_str is required to __init__ ThermoFisherGetEntity instance')
        else:
            self.cmd_str = get_str
        Entity.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        # setup cmd here
        logger.debug(f'raw cmd string is {self.cmd_str}')
        logger.debug(f'type cmd is {type(self.cmd_str.encode())}')
        logger.debug(f"type of {b'\x00'} is {type(b'\x00')}")
        to_send = [self.cmd_str.encode() + b'\x00']
        result = self.service.send_to_device(to_send)
        logger.debug(f'raw result is: {result}')

        # do something here
        decimal = 10.**(-int(result[0], 16))
        unit = self.units[int(result[1], 16)]
        value = float(int(result[2:], 16))

        #result = "%f %s"%(value*decimal, unit)
        result = value*decimal

        return result

    def on_set(self, value):
        to_send = [cmd]
        result = self.service.send_to_device(to_send)
        logger.debug(f'raw result is: {result}')
        # do something here
        return result
