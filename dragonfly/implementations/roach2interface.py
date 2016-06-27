# -*- coding: utf-8 -*-
"""
"""


from __future__ import absolute_import

# standard imports
import logging


# internal imports
from dripline import core

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
                 instrument_setup_filename_prefix=None,
                 mask_filename_prefix=None,
                 
                 hf_lo_freq=24.2e9,
                 analysis_bandwidth=50e6,
                 **kwargs):
        #DAQProvider.__init__(self, **kwargs)
        #EthernetProvider.__init__(self, **kwargs)
       
        self.roach2_hostname = roach2_hostname
        self._hf_lo_freq = hf_lo_freq
        self._analysis_bandwidth = analysis_bandwidth
        
        core.Provider.__init__(self, **kwargs)
        
        
        #connect to roach, pre-configure and start streaming data packages'''
        try:
            super(ArtooDaq, self).__init__(roach2_hostname, boffile='latest-built')
        except:
            logger.error('The Roach2 could not be setup or configured. '
                            'Possibly another service is already using it and closing that service might solve the problem')
        
        

    @property
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