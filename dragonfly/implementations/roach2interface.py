# -*- coding: utf-8 -*-
"""
"""


from __future__ import absolute_import

# standard imports
import logging
#import uuid

# internal imports
from dripline import core
#from .ethernet_provider import EthernetProvider

#phasmid import
try:
    from r2daq import ArtooDaq
    
except ImportError:
    
    
    class ArtooDaq(object):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Dependency <ArtooDaq> not found but is required for roach2 support")
    


__all__ = []

logger = logging.getLogger(__name__)


__all__.append('Roach2AcquisitionInterface')
class Roach2Provider(ArtooDaq, core.Provider):
    '''
    A DAQProvider for interacting with the Roach
    '''
    def __init__(self,
                 roach2_hostname = 'led',
                 do_ogp_cal=False,
                 do_adcif_cal=False,
                 source_ip = None,
                 source_port = None,
                 dest_ip = None,
                 dest_port = None,
                 dest_mac = None,
                                  
                 hf_lo_freq=24.2e9,
                 analysis_bandwidth=50e6,
                 
                 **kwargs):
        #DAQProvider.__init__(self, **kwargs)
        #EthernetProvider.__init__(self, **kwargs)
       
        self.roach2_hostname = roach2_hostname
        self._hf_lo_freq = hf_lo_freq
        self._analysis_bandwidth = analysis_bandwidth
        self.do_ogp_cal = do_ogp_cal
        self.do_adcif_cal = do_adcif_cal
        self.source_ip = source_ip
        self.source_port = source_port
        self.dest_ip = dest_ip
        self.dest_port = dest_port
        self.dest_mac = dest_mac
        self.cfg_list = None
        
        
        core.Provider.__init__(self, **kwargs)
        
        
    def _finish_configure(self):
        
        if self.source_ip != None:
            cfg_a = self.make_interface_config_dictionary(self.source_ip, self.source_port,dest_ip,self.dest_port,dest_mac=self.dest_mac,tag='a') 
            #cfg_b = self.make_interface_config_dictionary('192.168.10.101',4000,'192.168.10.64',4001,dest_mac='00:60:dd:44:91:e8',tag='b') 
            self.cfg_list = [cfg_a] 
        
        
        #connect to roach, pre-configure and start streaming data packages'''
        try:
            super(ArtooDaq, self).__init__(self.roach2_hostname, boffile='latest-built',do_ogp_cal=self.do_ogp_cal,do_adcif_cal=self.do_adcif_cal,ifcfg=self.cfg_list)
        except:
            logger.error('The Roach2 could not be setup or configured. '
                            'Possibly another service is already using it and closing that service might solve the problem')
        
        

   
    def is_running(self):
        logger.info('Checking whether ROACH2 is streaming data packages')
        pkts = self.grab_packets(n=1,dsoc_desc=("10.0.11.1",4001),close_soc=True)
        x = pkts[0].interpret_data()
        if len(x)>0:
            logger.info('The Roach2 is streaming data')
        else:
            logger.error('no data packages could be grabbed')
            raise core.DriplineInternalError('no streaming data')
        return
    
    def set_cf(self, freq):
        return
    def set_gain(self,gain):
        return
        
    def set_fft_shift(self,shift):
        return