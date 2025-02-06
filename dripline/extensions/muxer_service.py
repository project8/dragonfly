'''
A class to interface with the multiplexer aka muxer instrument
'''

from dripline.core import ThrowReply, Entity, calibrate
from dripline.implementations import EthernetSCPIService

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
