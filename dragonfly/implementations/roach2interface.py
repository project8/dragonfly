# -*- coding: utf-8 -*-
"""
"""


from __future__ import absolute_import

# standard imports
import logging
import uuid
import signal


# internal imports
from dripline import core
from .ethernet_provider import EthernetProvider


logger = logging.getLogger(__name__)


#phasmid import


try:

    from .r2daq import ArtooDaq
    logger.info('Imported ArtooDaq')
    
except ImportError:
       
    class ArtooDaq(object):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Dependency <ArtooDaq> not found but is required for roach2 support. Maybe check out PYTHONPATH")
    


__all__ = []




__all__.append('Roach2Provider')
class Roach2Provider(ArtooDaq, core.Provider):
    '''
    A DAQProvider for interacting with the Roach
    '''
    def __init__(self, **kwargs):

                 
        for i in kwargs:
            print(i)

        
        core.Provider.__init__(self, **kwargs)
        
        
        
__all__.append('Roach2Interface')
class Roach2Interface(Roach2Provider, EthernetProvider):
    def __init__(self,
                 roach2_hostname = 'led',
                 do_ogp_cal=False,
                 do_adcif_cal=False,
                 source_ip = None,
                 source_port = None,
                 dest_ip = None,
                 dest_port = None,
                 dest_mac = None,
                 daq_name = None,
                 channel_tag = 'a',
                 central_freq = 1234e6,
                                  
                 hf_lo_freq=24.2e9,
                 analysis_bandwidth=50e6,
                 
                 **kwargs):


        
        Roach2Provider.__init__(self, **kwargs)
      
        
        
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
        self.daq_name = daq_name
        self.channel_tag = channel_tag
        self.central_freq = central_freq


  
    def _finish_configure(self):
        logger.info('Configuring ROACH2, this will take a while.... no news is good news.')
        if self.source_ip != None:
            cfg_a = self.make_interface_config_dictionary(self.source_ip, self.source_port,self.dest_ip,self.dest_port,dest_mac=self.dest_mac,tag='a') 
            #cfg_b = self.make_interface_config_dictionary('192.168.10.101',4000,'192.168.10.64',4001,dest_mac='00:60:dd:44:91:e8',tag='b') 
            
            self.cfg_list = [cfg_a] 
            logger.info(cfg_a)
            ArtooDaq.__init__(self, self.roach2_hostname, boffile='latest-build', do_ogp_cal=self.do_ogp_cal, do_adcif_cal=self.do_adcif_cal, ifcfg=self.cfg_list)
        #connect to roach, pre-configure and start streaming data packages'''
        else:
            logger.info('Configuring ROACH2 without specific IP settings')
            ArtooDaq.__init__(self, self.roach2_hostname, boffile='latest-build')
        
            
        #except:
        #    logger.error('The Roach2 could not be setup or configured. '
         #                   'Have you tried turning it off and on again?')
        
        

   
    def is_running(self):
        logger.info('Checking whether ROACH2 is streaming data packages')
        
        try:
            pkts = ArtooDaq.grab_packets(self, n=1,dsoc_desc=("10.0.11.1",4001),close_soc=True)
            x = pkts[0].interpret_data()
            if len(x)>0:
                logger.info('The Roach2 is streaming data')
                return_content = True
            else:
                logger.error('No data packages could be grabbed.')
                raise core.DriplineInternalError('The Roach2 is not streaming data')
        except:                 
            return_content = False
            logger.info('Pinging ROACH2')
            
            import os
            
            response = os.system("ping -c 1 " + self.roach2_hostname)

            #and then check the response...
            if response == 0:
              logger.info('ROACH2 is running but phasmid is not.')
            else:
              logger.info('ROACH2 is switched off or not connected to the network.')

        return return_content
        
        
    def set_central_frequency(self, cf):
        logger.info('setting central frequency of channel {} to {}'.format(self.channel_tag, cf))
        ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=self.channel_tag)
        
    def get_central_frequency(self):
        cfg = ArtooDaq.read_ddc_1st_config(self, tag=self.channel_tag)
        logger.info('Central frequency of channel {} to {}'.format(self.channel_tag, cfg['digital']))
        
        
    def set_gain(self, gain):
        if gain>5 and gain <10:
            logger.info('setting gain of channel {} to {}'.format(self.channel_tag, gain))
            ArtooDaq.set_gain(self, gain, tag=self.channel_tag)
            return True
        else:
            logger.error('Only gain values between 5 and 10 are allowed')
            return False
        
    def set_fft_shift(self, shift):
        logger.info('setting fft shift of channel {} to {}'.format(self.channel_tag, shift))
        ArtooDaq.set_fft_shift(self, shift, tag=self.channel_tag)
        

