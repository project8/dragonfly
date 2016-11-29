from __future__ import absolute_import

from dripline.core import Endpoint, fancy_doc
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
        if scan_interval == 0:
            raise ValueError("scan interval must be > 0")
        self.scan_interval = scan_interval

    def conf_scan_list(self, *args, **kwargs):
        '''
        conf_scan_list loops over the provider's internal list of endpoints and attempts to configure each
        '''
        self.send(['ABOR'])
        self.send(['*CLS'])

        ch_scan_list = list()
        for child in self.endpoints:

            if not isinstance(self.endpoints[child], MuxerGetSpime):
                continue
            elif self.endpoints[child].conf_str == False:
                ch_scan_list.append(self.endpoints[child].ch_number)
                self.endpoints[child].log_interval = self.scan_interval
            else:
                self.send([self.endpoints[child].conf_str])
                self.send(['SYST:ERR?'])
                ch_scan_list.append(str(self.endpoints[child].ch_number))
                self.endpoints[child].log_interval = self.scan_interval

        scan_list_cmd = 'ROUT:SCAN (@{})'.format(','.join(ch_scan_list))
        logger.debug('sending scan list command:\n{}'.format(scan_list_cmd))
        self.start_scan(scan_list_cmd)

    def start_scan(self, scan_list_cmd):
        '''
        start_scan sets up the scan list (with all formatted channels), configures the trigger system, and initiates the scan
        '''

        self.send([scan_list_cmd])

        self.send(['TRIG:SOUR TIM', 'TRIG:COUN INF', 'TRIG:TIM {}'.format(self.scan_interval)])

        self.send(['INIT'])
