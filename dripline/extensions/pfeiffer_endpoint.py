from dripline.core import Entity, calibrate, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('PfeifferEntity')
class PfeifferEntity(Entity):
    '''
    Pfeiffer Entity implements the Telegram protocol by Pfeiffer. 
    The message contains commands in form of parameter numbers and different length data that depend on the given datatype.
    Conversion of datatypes and checksum checking are implemented.
    '''

    _datatype = {"bool_old": 6, 
                 "uint":     6, 
                 "ureal":    6, 
                 "string":   6, 
                 "bool":     1, 
                 "ushort":   3, 
                 "uexpo":    6, 
                 "str16":   16, 
                 "str8":     8, 
                 "query":    2
                 }
    
    def __init__(self,
                 parameter = 303,
                 datatype = "uexpo",
                 unit_address = 1,
                 **kwargs):
        '''
        Args:
            parameter (int): number of the parameter as documented in the manual"
            datatype (str): one of ["bool_old", "uint", "ureal", "string", "bool", "ushort", "uexpo", "str16", "str8"
            unit_address (int): number of the unit address, allwoed range: 1-16
        '''
        Entity.__init__(self, **kwargs)
        self.parameter = parameter
        self.datatype = datatype
        self.unit_address = unit_address

    def get_checksum(self, string):
        return sum([ord(c) for c in string])%256

    def format_value(self, value):
        if self.datatype == "bool_old":
            return "111111" if value else "000000"
        if self.datatype == "bool":
            return "1" if value else "0"
        if self.datatype == "string":
            return f"{value:6s}"
        if self.datatype == "str8":
            return f"{value:8s}"
        if self.datatype == "str16":
            return f"{value:16s}"
        if self.datatype == "uint":
            return f"{value:06d}"
        if self.datatype == "ushort":
            return f"{value:03d}"
        if self.datatype == "ureal":
            val = int(value*100)
            return f"{val:06d}"
        if self.datatype == "uexpo":
            expon = int(np.log10(val)//1)
            val = int(val/10**expon*1000)
            expon_mod = expon - 20
            return f"{val:04d}{expon_mod:02d}"
        return value

    def unformat_value(self, value):
        if value in ["NO_DEF", "_RANGE", "_LOGIC"]:
            raise ValueError(f"Device responded with an error {value}")
        if len(value) != self._datatype[self.datatype]:
            raise ValueError(f"data does not match length of datatype")

        if self.datatype ==  "bool_old":
            return value == "111111"
        if self.datatype == "bool":
            return value == 1 
        if self.datatype in ["string", "str16", "str8"]:
            return value
        if self.datatype in ["uint", "ushort"]:
            return int(value)
        if self.datatype == "ureal":
            return int(value)/100.
        if self.datatype == "uexpo":
            return int(value[:4])/1000. * 10**(int(value[4:]) - 20)
        return value

    def disensemble_result(self, reply):
        if self.get_checksum(reply[:-3]) != int(reply[-3:]):
            logger.warning("checksum not matching")
        # split message into its constituents, we do not need all of them
        # address = int(reply[:3])
        # action = reply[3:5]
        # parameter = int(reply[5:8])
        length = int(reply[8:10])
        data = reply[10:10+length]
        return data

    @calibrate()
    def on_get(self):
        value = "=?"
        cmd = f"{self.unit_address:03d}00{self.parameter:03d}{len(value):02d}{value}"
        cs = self.get_checksum(cmd) 
        cmd += f"{cs:03d}"
        result = self.service.send_to_device([cmd])
        logger.debug(f'raw result is: {result}')
        result = self.disensemble_result(result)
        logger.debug(f'disensembled result is: {result}')
        result = self.unformat_value(result)
        logger.debug(f'unformated result is: {result}')
        return result

    def on_set(self, value):
        value = self.format_value(value)
        cmd = f"{self.unit_address:03d}10{self.parameter:03d}{len(value):02d}{value}"
        cs = self.get_checksum(cmd) 
        cmd += f"{cs:03d}"
        result = self.service.send_to_device([cmd])
        logger.debug(f'raw result is: {result}')
        result = self.disensemble_result(result)
        logger.debug(f'disensembled result is: {result}')
        result = self.unformat_value(result)
        logger.debug(f'unformated result is: {result}')
        return result 

__all__.append('PfeifferGetEntity')
class PfeifferGetEntity(PfeifferEntity):
    '''
    Identical to PfeifferEntity, but with an explicit exception if on_set is attempted
    '''

    def __init__(self, **kwargs):
        PfeifferEntity.__init__(self, **kwargs)

    def on_set(self, value):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support set")


__all__.append('PfeifferSetEntity')
class PfeifferSetEntity(PfeifferEntity):
    '''
    Modelled on PfeifferEntity, but with an explicit exception if on_get is attempted.
    '''

    def __init__(self, **kwargs):
        PfeifferEntity.__init__(self, **kwargs)

    def on_get(self):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support get")
