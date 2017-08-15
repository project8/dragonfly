'''
A Spime is an enhanced implementation of a Dripline Endpoint with simple logging capabilities.
The spimes defined here are more broad-ranging than a single service, obviating the need to define new spimes for each new service or provider.

When implementing a spime, please remember:
- All communication must be configured to return a response.  If no useful get is possible, consider a *OPC?
- set_and_check is a generally desirable functionality

Spime catalog (in order of ease-of-use):
- SimpleSCPISpime: quick and simple minimal spime
-* SimpleSCPIGetSpime/SimpleSCPISetSpime: limited instance of above with disabled Get/Set
- FormatSpime: utility spime with expanded functionality
- ErrorQueueSpime: spime for iterating through error queue to clear it and return all erros
- GPIOSpime: spime to handle GPIO pin control on RPi
- IonGaugeSpime: spime to handle communication with Lesker/B-RAX pressure gauges
- LeakValveSpime: spime to handle VAT leak valve get responses
- LockinSpime: spime to handle antiquated lockin IEEE 488 formatting
-* LockinGetSpime: limited instance of above with disabled Set
- Max31856Spime: spime to handle thermocouple reading through GPIO on RPi
- MuxerGetSpime: spime to handle glenlivet muxer formatting
- ProviderAttributeSpime: spime for provider @property
'''
from __future__ import absolute_import

# re used for FormatSpime
import re

# RPi.GPIO used for GPIOSpime (directly) and Max31856Spime (indirectly)
try:
    import RPi.GPIO as GPIO
except ImportError:
    pass

from dripline.core import Spime, fancy_doc, calibrate
from dripline.core.exceptions import *

from .spime_calibrations import *

import logging
logger = logging.getLogger(__name__)
__all__ = []


__all__.append('SimpleSCPISpime')
@fancy_doc
class SimpleSCPISpime(Spime):
    '''
    Convenience spime for interacting with SCPI endpoints that support basic set and query syntax.
    '''

    def __init__(self,
                 base_str=None,
                 **kwargs):
        '''
        base_str (str): string used to generate SCPI commands; get will be of the form "base_str?"; set will be of the form "base_str <value>;base_str?"
        '''
        if base_str is None:
            raise DriplineValueError('<base_str> is required to __init__ SimpleSCPISpime instance')
        else:
            self.cmd_base = base_str
        Spime.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        to_send = [self.cmd_base + '?']
        result = self.provider.send(to_send)
        logger.debug('raw result is: {}'.format(result))
        return result

    def on_set(self, value):
        to_send = ['{0} {1};{0}?'.format(self.cmd_base,value)]
        return self.provider.send(to_send)


__all__.append('SimpleSCPIGetSpime')
@fancy_doc
class SimpleSCPIGetSpime(SimpleSCPISpime):
    '''
    Identical to SimpleSCPISpime, but with an explicit exception if on_set is attempted
    '''

    def __init__(self, **kwargs):
        SimpleSCPISpime.__init__(self, **kwargs)

    def on_set(self, value):
        raise DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))


__all__.append('SimpleSCPISetSpime')
@fancy_doc
class SimpleSCPISetSpime(SimpleSCPISpime):
    '''
    Modelled on SimpleSCPISpime, but with an explicit exception if on_get is attempted, and on_set return query is *OPC? instead of base_str?
    '''

    def __init__(self, **kwargs):
        SimpleSCPISpime.__init__(self, **kwargs)

    def on_get(self):
        raise DriplineMethodNotSupportedError('getting not available for {}'.format(self.name))

    def on_set(self, value):
        to_send = ['{} {};*OPC?'.format(self.cmd_base,value)]
        return self.provider.send(to_send)


__all__.append('FormatSpime')
@fancy_doc
class FormatSpime(Spime):
    '''
    Utility spime allowing arbitrary set and query syntax and formatting for more complicated usage cases
    No assumption about SCPI communication syntax.
    '''

    def __init__(self,
                 get_str=None,
                 get_reply_float=False,
                 set_str=None,
                 set_value_lowercase=True,
                 set_value_map=None,
                 **kwargs):
        '''
        get_str (str): sent verbatim in the event of on_get; if None, getting of endpoint is disabled
        get_reply_float (bool): apply special formatting to get return
        set_str (str): sent as set_str.format(value) in the event of on_set; if None, setting of endpoint is disabled
        set_value_lowercase (bool): default option to map all string set value to .lower()
            **WARNING: never set to False is using a set_value_map
        set_value_map (dict): dictionary of mappings for values to on_set; note that the result of set_value_map[value] will be used as the input to set_str.format(value) if this dict is present
        '''
        Spime.__init__(self, **kwargs)
        self._get_reply_float = get_reply_float
        self._get_str = get_str
        self._set_str = set_str
        self._set_value_map = set_value_map
        if set_value_map is not None and not isinstance(set_value_map, dict):
            raise DriplineValueError("Invalid set_value_map config for {}; type is {} not dict".format(self.name, type(set_value_map)))
        self._set_value_lowercase = set_value_lowercase
        if set_value_map is not None and not set_value_lowercase:
            raise DriplineValueError("Invalid config option for {} with set_value_map and set_value_lowercase=False".format(self.name))

    @calibrate()
    def on_get(self):
        if self._get_str is None:
            raise DriplineMethodNotSupportedError('<{}> has no get string available'.format(self.name))
        result = self.provider.send([self._get_str])
        logger.debug('result is: {}'.format(result))
        if self._get_reply_float:
            logger.debug('desired format is: float')
            formatted_result = map(float, re.findall("[-+]?\d+\.\d+",format(result)))
            # formatted_result = map(float, re.findall("[-+]?(?: \d* \. \d+ )(?: [Ee] [+-]? \d+ )",format(result)))
            logger.debug('formatted result is {}'.format(formatted_result[0]))
            return formatted_result[0]
        return result

    def on_set(self, value):
        if self._set_str is None:
            raise DriplineMethodNotSupportedError('<{}> has no set string available'.format(self.name))
        if isinstance(value, (str,unicode)) and self._set_value_lowercase:
            value = value.lower()
        if self._set_value_map is None:
            mapped_value = value
        elif isinstance(self._set_value_map, dict):
            mapped_value = self._set_value_map[value]
        logger.debug('value is {}; mapped value is: {}'.format(value, mapped_value))
        return self.provider.send([self._set_str.format(mapped_value)])


__all__.append('ErrorQueueSpime')
class ErrorQueueSpime(Spime):
    '''
    Spime for polling error queue until empty.
    '''

    def __init__(self,
                 get_str,
                 empty_str,
                 **kwargs):
        '''
        get_str (str): channel number for endpoint
        empty_key (str): modify get string to return float instead of int
        '''
        Spime.__init__(self, **kwargs)
        self._get_str = get_str
        self._empty_str = empty_str

    @calibrate()
    def on_get(self):
        result = [None]
        while result[-1] != self._empty_str:
            result.append( self.provider.send([self._get_str]) )
        result.pop(0)
        return ';'.join(result)

    def on_set(self, value):
        raise DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))


__all__.append('GPIOSpime')
@fancy_doc
class GPIOSpime(Spime):
    '''
    Spime for interacting with GPIO pins on Raspberry Pi
    '''
    def __init__(self,
                 inpin=None,
                 outpin=None,
                 set_value_map=None,
                 **kwargs
                 ):
        '''
        inpin (int||list): pin(s) to read for get
        outpin (int||list): pin(s) to program for set
        set_value_map (dict): dictionary of mappings for values to on_set; note that the result of set_value_map[value] will be used as the input to set_str.format(value) if this dict is present
        '''
        if not 'GPIO' in globals():
            raise ImportError('RPi.GPIO not found, required for GPIOSpime class')
        if 'get_on_set' not in kwargs:
            kwargs['get_on_set'] = True
        Spime.__init__(self, **kwargs)

        if inpin is not None:
            if not isinstance(inpin, list):
                inpin = [inpin]
            if not all(isinstance(pin, int) for pin in inpin):
                raise exceptions.DriplineValueError("Invalid inpin <{}> for {}, requires int or list of int".format(repr(inpin), self.name))
        self._inpin = inpin
        if outpin is not None:
            if not isinstance(outpin, list):
                outpin = [outpin]
            if not all(isinstance(pin,int) for pin in outpin):
                raise exceptions.DriplineValueError("Invalid outpin <{}> for {}, requires int or list of int".format(repr(outpin), self.name))
        self._outpin = outpin
        if set_value_map is not None and not isinstance(set_value_map, dict):
            raise DriplineValueError("Invalid set_value_map config for {}; type is {} not dict".format(self.name, type(set_value_map)))
        self._set_value_map = set_value_map

    @calibrate()
    def on_get(self):
        if self._inpin is None:
            raise DriplineMethodNotSupportedError("<{}> has no get pin available".format(self.name))
        result = 0
        for i, pin in enumerate(self._inpin):
            result += GPIO.input(pin)<<i
        return result

    def on_set(self, value):
        if self._outpin is None:
            raise DriplineMethodNotSupportedError("<{}> has no set pin available".format(self.name))
        if isinstance(self._set_value_map, dict) and value in self._set_value_map:
            raw_value = value
            if isinstance(value, (str,unicode)):
                value = value.lower()
            value = self._set_value_map[value]
            logger.debug('raw set value is {}; mapped value is: {}'.format(raw_value, value))
        GPIO.output(self._outpin, value)
        if not all(GPIO.input(pin)==value for pin in self._outpin):
            raise DriplineHardwareError("Error setting GPIO output pins")


__all__.append('IonGaugeSpime')
@fancy_doc
class IonGaugeSpime(Spime):
    '''
    Spime for interacting with ion gauges over RS485
    '''

    def __init__(self,
                 get_str=None,
                 set_str=None,
                 set_value_map=None,
                 **kwargs):
        '''
        get_str (str): sent verbatim in the event of on_get
        set_str (str): sent as set_str.format(value) in the event of on_set; if None, setting of endpoint is disabled
        set_value_map (dict): dictionary of mappings for values to on_set; no error if not value not present in dictionary keys
        '''
        Spime.__init__(self, **kwargs)
        self._get_str = get_str
        self._address = '*'+get_str[1:3]
        self._set_str = set_str
        self._set_value_map = set_value_map
        if set_value_map is not None and not isinstance(set_value_map, dict):
            raise DriplineValueError("Invalid set_value_map config for {}; type is {}, not dict".format(self.name, type(set_value_map)))

    @calibrate()
    def on_get(self):
        result = self.provider.send([self._get_str])
        if result[:3] != self._address:
            raise DriplineHardwareError("Response address mismatch!  Response address is {}, expected address is {}".format(result, self._address))
        return result[4:]

    def on_set(self, value):
        if self._set_str is None:
            raise DriplineMethodNotSupportedError("setting not available for {}".format(self.name))
        if isinstance(value, (str,unicode)):
            value = value.lower()
        if (self._set_value_map is not None) and (value in self._set_value_map):
            mapped_value = self._set_value_map[value]
            logger.debug('value is {}; mapped value is: {}'.format(value, mapped_value))
        else:
            mapped_value = value
            logger.debug('value not in set_value_map, using given value of {}'.format(mapped_value))
        result = self.provider.send([self._set_str.format(mapped_value)])
        if result != self._address + ' PROGM OK':
            raise DriplineHardwareError("Error response returned when setting endpoint {}".format(self.name))
        return


__all__.append('LeakValveSpime')
@fancy_doc
class LeakValveSpime(FormatSpime):
    '''
    Special implementation of FormatSpime for T2 VAT leak valve
    on_get has specific formatting rules, otherwise just a FormatSpime
    '''

    def __init__(self,
                 **kwargs):
        '''
        '''
        FormatSpime.__init__(self, **kwargs)

    @calibrate([leak_valve_status_calibration])
    def on_get(self):
        # if self._get_str is None:
        #     raise DriplineMethodNotSupportedError('<{}> has no get string available'.format(self.name))
        result = self.provider.send([self._get_str])
        logger.debug('raw result is: {}'.format(repr(result)))
        # Leak valve returns pseduo-reply_echo_cmd, only need treatment on get
        result = result[len(self._get_str):]
        # Leak valve has zero-padded int responses which get badly calibrated
        result = result.lstrip('0')
        if result == '':
            result = '0'
        logger.debug('formatted result is: {}'.format(repr(result)))
        return result


__all__.append('LockinSpime')
class LockinSpime(FormatSpime):
    '''
    Spime for communication with lockin endpoints.  Uses antiquated IEEE 488 standard.
    '''

    def __init__(self,
                 property_key,
                 get_float=False,
                 **kwargs):
        '''
        property_key (str): channel number for endpoint
        get_float (bool): modify get string to return float instead of int
        '''
        FormatSpime.__init__(self, **kwargs)
        if get_float:
            self._get_str = property_key + '.'
        else:
            self._get_str = property_key
        self._set_str = property_key

    @calibrate([acquisition_calibration, status_calibration])
    def on_get(self):
        return self.provider.send([self._get_str])

    def on_set(self, value):
        if not isinstance(value, int):
            raise DriplineValueError('Set value of LockinSpime {} must be an int'.format(self.name))
        to_send = "{0} {1}; {0}".format(self._set_str, value)
        return self.provider.send([to_send])


__all__.append('LockinGetSpime')
class LockinGetSpime(LockinSpime):
    '''
    Identical to LockinSpime, but with an explicit exception if on_set attempted
    '''

    def __init__(self, **kwargs):
        LockinSpime.__init__(self, **kwargs)

    def on_set(self, value):
        raise DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))


__all__.append('Max31856Spime')
@fancy_doc
class Max31856Spime(Spime):
    '''
    Spime for interacting with Max31856 temperature sensor via GPIO pins on Raspberry Pi
    '''
    def __init__(self,
                 **kwargs
                 ):
        '''
        SPI GPIO pins on RPi must be configured via setup_calls with configure_max31856 method
        '''
        if not 'GPIO' in globals():
            raise ImportError('RPi.GPIO not found, required for Max31856Spime class')
        Spime.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        result = self.provider.max31856.read_temp_c()
        return result

    def on_set(self, value):
        raise DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))

__all__.append('MuxerGetSpime')
class MuxerGetSpime(Spime):
    '''
    Spime for communication with muxer endpoints.  No set functionality.
    '''

    def __init__(self,
                 ch_number,
                 conf_str=None,
                 **kwargs):
        '''
        ch_number (int): channel number for endpoint
        conf_str (str): used by MuxerProvider to configure endpoint scan
        '''
        if conf_str is None:
           raise DriplineValueError('conf_str required for MuxerGetSpime endpoint {}, set to False to not configure'.format(self.name))
        self.get_str = "DATA:LAST? (@{})".format(ch_number)
        self.ch_number = ch_number
        self.conf_str = conf_str.format(ch_number)
        Spime.__init__(self, **kwargs)

    @calibrate([pt100_calibration, cernox_calibration, cernox_calibration_chebychev])
    def on_get(self):
        result = self.provider.send([self.get_str.format(self.ch_number)])
        logger.debug('very raw is: {}'.format(result))
        return result.split()[0]

    def on_set(self, value):
        raise DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))


__all__.append('RelaySpime')
class RelaySpime(FormatSpime):
    '''
    Convenience spime for communication with relay endpoints.
    '''

    def __init__(self,
                 ch_number,
                 relay_type=None,
                 **kwargs):
        '''
        ch_number (int): channel number for endpoint
        relay_type (None,'relay','polarity','switch'): automatically configure set_value_map and calibration dictionaries (overwriteable)
        '''
        # Default get/set strings
        if 'get_str' not in kwargs:
            if relay_type=='relay' or relay_type=='polarity':
                kwargs.update( {'get_str':':ROUTE:OPEN? (@{})'.format(ch_number)} )
            elif relay_type=='switch':
                kwargs.update( {'get_str':':ROUTE:CLOSE? (@{})'.format(ch_number)} )
        if 'set_str' not in kwargs:
            kwargs.update( {'set_str':':ROUTE:{{}} (@{});{}'.format(ch_number,kwargs['get_str'])} )
        # Default kwargs for get_on_set and set_value_lowercase
        if 'get_on_set' not in kwargs:
            kwargs.update( {'get_on_set':True} )
        if 'set_value_lowercase' not in kwargs:
            kwargs.update( {'set_value_lowercase':True} )
        # Default set_value_map and calibration for known relay types (relay, polarity, switch)
        if relay_type == 'relay':
            if 'set_value_map' not in kwargs:
                kwargs.update( { 'set_value_map' : {1: 'OPEN',
                                                    0: 'CLOSE',
                                                    'on': 'OPEN',
                                                    'off': 'CLOSE',
                                                    'enable': 'OPEN',
                                                    'disable': 'CLOSE'} } )
            if 'calibration' not in kwargs:
                kwargs.update( { 'calibration' : {'1': 'enabled',
                                                  '0': 'disabled'} } )
        elif relay_type == 'polarity':
            if 'set_value_map' not in kwargs:
                kwargs.update( { 'set_value_map' : {1: 'OPEN',
                                                    0: 'CLOSE',
                                                    'positive': 'OPEN',
                                                    'negative': 'CLOSE'} } )
            if 'calibration' not in kwargs:
                kwargs.update( { 'calibration' : {'1': 'positive',
                                                  '0': 'negative'} } )
        elif relay_type == 'switch':
            if 'set_value_map' not in kwargs:
                kwargs.update( { 'set_value_map' : {0: 'OPEN',
                                                    1: 'CLOSE',
                                                    'off': 'OPEN',
                                                    'on': 'CLOSE',
                                                    'disable': 'OPEN',
                                                    'enable': 'CLOSE'} } )
            if 'calibration' not in kwargs:
                kwargs.update( { 'calibration' : {'0': 'disabled',
                                                  '1': 'enabled'} } )
        elif relay_type is not None:
            raise DriplineValueError("Invalid relay_type for {}; expect 'relay' or 'polarity'".format(self.name))
        FormatSpime.__init__(self, **kwargs)


__all__.append('ProviderAttributeSpime')
class ProviderAttributeSpime(Spime):
    '''
    Spime allowing communication with provider property.
    '''

    def __init__(self,
                 attribute_name,
                 disable_set=False,
                 **kwargs):
       Spime.__init__(self, **kwargs)
       self._attribute_name = attribute_name
       self._disable_set = disable_set

    @calibrate()
    def on_get(self):
        return getattr(self.provider, self._attribute_name)

    def on_set(self, value):
        if self._disable_set:
            raise DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))
        setattr(self.provider, self._attribute_name, value)
