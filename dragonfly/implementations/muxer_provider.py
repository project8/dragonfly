from __future__ import absolute_import
import socket
import threading
import types

from dripline.core import Provider, Endpoint, exceptions
from dragonfly.implementations import EthernetProvider
from dragonfly.implementations import MuxerGetSpime
from dripline.core.utilities import fancy_doc

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

                ch_scan_list = list()

                self.send(['ABOR'])
                self.send(['*CLS']) 

                for child in self.endpoints:

                        if not isinstance(self.endpoints[child], MuxerGetSpime):
                                continue 
                        if self.endpoints[child].conf_str == None: 
                                logger.error('conf_str value is required to configure {}'.format(self.endpoints[child].name))  
                                raise exceptions.DriplineWarning('if {} is not to be configured, please set conf_str to False'.format(self.endpoints[child].name))
                                continue 
                        elif self.endpoints[child].conf_str == False: 
                                ch_scan_list.append(self.endpoints[child].ch_number)
                                continue 
                        else: 
                                logger.debug('sending:\n{}'.format(self.endpoints[child].conf_str.format(self.endpoints[child].ch_number))) 
                                self.send([self.endpoints[child].conf_str.format(self.endpoints[child].ch_number)])
                                self.send(['SYST:ERR?'], endpoint_name=self.endpoints[child].name, endpoint_ch_number=self.endpoints[child].ch_number)
                                                                                                                                 
                                ch_scan_list.append(str(self.endpoints[child].ch_number)) 

                scan_list_cmd = 'ROUT:SCAN (@{})'.format(','.join(ch_scan_list))
                logger.debug('sending scan list command:\n{}'.format(scan_list_cmd))
                self.start_scan(scan_list_cmd) 

        def start_scan(self, scan_list_cmd):

                self.send([scan_list_cmd])

                self.send(['TRIG:SOUR TIM', 'TRIG:COUN INF', 'TRIG:TIM {}'.format(self.scan_interval)])

                self.send(['INIT'])
