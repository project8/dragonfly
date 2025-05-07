'''
A class to interface with the multiplexer aka muxer instrument
'''

from dripline.core import ThrowReply, Entity, calibrate
from dripline.implementations import EthernetSCPIService, FormatEntity

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append('MuxerService')

class MuxerService(EthernetSCPIService):
    '''
    Provider to interface with muxer
    '''

    def __init__(self, scan_interval=0,**kwargs):
        '''
        scan_interval (int): time between scans in seconds
        '''
        EthernetSCPIService.__init__(self,**kwargs)
        if scan_interval <= 0:
            raise ThrowReply('service_error_invalid_value', 'scan interval must be > 0')
        self.scan_interval = scan_interval
        self.configure_scan()

    def configure_scan(self, *args, **kwargs):
        '''
        loops over the provider's internal list of endpoints and attempts to configure each, then configures and begins scan
        '''
        self.send_to_device(['ABOR;*CLS;*OPC?'])

        ch_scan_list = list()
        for childname, child in self.sync_children.items():

            if not isinstance(child, MuxerGetEntity):
                continue
            error_data = self.send_to_device([child.conf_str+';*OPC?','SYST:ERR?'])
            if error_data != '1;+0,"No error"':
                logger.critical('Error detected; cannot configure muxer')
                raise ThrowReply('resource_error',
                                f'{error_data} when attempting to configure endpoint <{childname}>')

            ch_scan_list.append(str(child.ch_number))
            child.log_interval = self.scan_interval

        scan_list_cmd = 'ROUT:SCAN (@{})'.format(','.join(ch_scan_list))
        self.send_to_device([scan_list_cmd+';*OPC?',\
                   'TRIG:SOUR TIM;*OPC?',\
                   'TRIG:COUN INF;*OPC?',\
                   'TRIG:TIM {};*OPC?'.format(self.scan_interval),\
                   'INIT;*ESE?'])


__all__.append('MuxerGetEntity')
class MuxerGetEntity(Entity):
    '''
    Entity for communication with muxer endpoints.  No set functionality.
    '''

    def __init__(self,
                 ch_number,
                 conf_str=None,
                 **kwargs):
        '''
        ch_number (int): channel number for endpoint
        conf_str (str): used by MuxerService to configure endpoint scan
        '''
        Entity.__init__(self, **kwargs)
        if conf_str is None:
            raise ThrowReply('service_error_invalid_value',
                            f'<conf_str> required for MuxerGetEntity {self.name}')
        self.get_str = "DATA:LAST? (@{})".format(ch_number)
        self.ch_number = ch_number
        self.conf_str = conf_str.format(ch_number)

    @calibrate()
    def on_get(self):
        result = self.service.send_to_device([self.get_str.format(self.ch_number)])
        logger.debug('very raw is: {}'.format(result))
        return result.split()[0]

    def on_set(self, value):
        raise ThrowReply('message_error_invalid_method',
                        f'endpoint {self.name} does not support set')



__all__.append('MuxerRelay')
class MuxerRelay(FormatEntity):
    ''' 
    Entity to communicate with relay cards in muxer,
    '''
    def __init__(self,
                 ch_number,
                 relay_type=None,
                 **kwargs):
        '''
        ch_number (int): channel number for endpoint
        relay_type (None,'relay','polarity','switch'): automatically configure set_value_map and calibration dictionaries (overwriteable)
        '''

        # default get/set strings
        if get_str not in kwargs:
            if relay_type=='relay' or relay_type=='polarity':
                kwargs.update( {get_str:':ROUTE:OPEN? (@{})'.format(ch_number)} )
            elif relay_type=='switch':
                kwargs.update( {get_str:':ROUTE:CLOSE? (@{})'.format(ch_number)} )
        if 'set_str' not in kwargs:
            kwargs.update( {'set_str':':ROUTE:{{}} (@{});{}'.format(ch_number,kwargs['get_str'])} )
        # Default kwargs for get_on_set and set_value_lowercase
        if 'get_on_set' not in kwargs:
            kwargs.update( {'get_on_set':True} )
        if 'set_value_lowercase' not in kwargs:
            kwargs.update( {'set_value_lowercase' :True} )
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
             raise ThrowReply("message_error_invalid_method",
                             f"endpoint {self.name} expect 'relay'or 'polarity'")

        FormatEntity.__init__(self, **kwargs)

