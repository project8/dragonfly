from __future__ import absolute_import

from dripline.core import Endpoint, fancy_doc, exceptions
from dragonfly.implementations import EthernetProvider, MuxerGetSpime

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append('MuxerProvider')

@fancy_doc
class MuxerProvider(EthernetProvider):

    def __init__(self, scan_interval=0,**kwargs):
        '''
        scan_interval (int): time between scans in seconds
        '''
        EthernetProvider.__init__(self,**kwargs)
        if scan_interval <= 0:
            raise exceptions.DriplineValueError("scan interval must be > 0")
        self.scan_interval = scan_interval

    def conf_scan_list(self, *args, **kwargs):
        '''
        loops over the provider's internal list of endpoints and attempts to configure each, then configures and begins scan
        '''
        self.send(['ABOR;*CLS;*OPC?'])

        ch_scan_list = list()
        for child in self.endpoints:

            if not isinstance(self.endpoints[child], MuxerGetSpime):
                continue
            elif self.endpoints[child].conf_str:
                error_data = self.send([self.endpoints[child].conf_str+';*OPC?',\
                                        'SYST:ERR?'])
                if error_data != '1;+0,"No error"':
                    logger.critical('Error detected; cannot configure muxer')
                    raise exceptions.DriplineHardwareError('{} when attempting to configure endpoint named "{}"'.format(error_data,child))

            ch_scan_list.append(str(self.endpoints[child].ch_number))
            self.endpoints[child].log_interval = self.scan_interval

        scan_list_cmd = 'ROUT:SCAN (@{})'.format(','.join(ch_scan_list))
        self.send([scan_list_cmd+';*OPC?',\
                   'TRIG:SOUR TIM;*OPC?',\
                   'TRIG:COUN INF;*OPC?',\
                   'TRIG:TIM {};*OPC?'.format(self.scan_interval),\
                   'INIT;*ESE?'])
