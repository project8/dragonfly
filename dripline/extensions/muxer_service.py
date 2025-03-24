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

    
    def pt100_calibration(resistance):
        '''Calibration for the (many) muxer pt100 temperature sensor endpoints'''
        r = resistance
        value = ((r < 2.2913) * ((3.65960-r)*(-6.95647+r/0.085)/1.36831 + (r-2.2913)*(10.83979+r/.191)/1.36831 ) + # extrapolation to too small temperature
            (2.2913 <= r and r < 3.65960) *((3.65960-r)*(-6.95647+r/0.085)/1.36831 + (r-2.2913)*(10.83979+r/.191)/1.36831 ) +
            (3.6596 <= r and r < 9.38650) *((9.38650-r)*(10.83979+r/0.191)/5.72690 + (r-3.6596)*(23.92640+r/.360)/5.72690) +
            (9.3865 <= r and r < 20.3800) *((20.3800-r)*(23.92640+r/0.360)/10.9935 + (r-9.3865)*(29.17033+r/.423)/10.9935) +
            (20.380 <= r and r < 29.9890) *((29.9890-r)*(29.17033+r/0.423)/9.54900 + (r-20.380)*(29.10402+r/.423)/9.54900) +
            (29.989 <= r and r < 50.7880) *((50.7880-r)*(29.10402+r/0.423)/20.7990 + (r-29.989)*(25.82396+r/.409)/20.7990) +
            (50.788 <= r and r < 71.0110) *((71.0110-r)*(25.82396+r/0.409)/20.2230 + (r-50.788)*(22.47250+r/.400)/20.2230) +
            (71.011 <= r and r < 90.8450) *((90.8450-r)*(22.47250+r/0.400)/19.8340 + (r-71.011)*(18.84224+r/.393)/19.8340) +
            (90.845 <= r and r < 110.354) *((110.354-r)*(18.84224+r/0.393)/19.5090 + (r-90.845)*(14.84755+r/.387)/19.5090) +
            (110.354 <= r and r < 185) * (14.84755+r/.387) +
            (185. <= r) * (0))
        if value == 0:
            value = None
        return value

    @calibrate([pt100_calibration])
    def on_get(self):
        result = self.service.send_to_device([self.get_str.format(self.ch_number)])
        logger.debug('very raw is: {}'.format(result))
        return result.split()[0]

    def on_set(self, value):
        raise ThrowReply('message_error_invalid_method',
                        f'endpoint {self.name} does not support set')
