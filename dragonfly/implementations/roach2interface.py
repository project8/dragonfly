# -*- coding: utf-8 -*-
"""
"""


from __future__ import absolute_import

# standard imports
import logging
#import uuid
#import signal
import os
import matplotlib.pyplot as plt
import numpy as np


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
            raise RuntimeError("Dependency <ArtooDaq> not found but is required for ROACH2 support.")



__all__ = []




__all__.append('Roach2Provider')
class Roach2Provider(ArtooDaq, core.Provider):
    '''
    A DAQProvider for interacting with the Roach
    '''
    def __init__(self, **kwargs):


        core.Provider.__init__(self, **kwargs)



__all__.append('Roach2Interface')
class Roach2Interface(Roach2Provider, EthernetProvider):
    def __init__(self,
                 roach2_hostname = 'led',
                 source_ip = None,
                 source_port = None,
                 source_mac = None,
                 dest_ip = None,
                 dest_port = None,
                 dest_mac = None,
                 daq_name = None,
                 channel_tag = 'a',
                 do_adc_ogp_calibration = False,
                 central_freq = 800e6,
                 gain = 7.0,

                 hf_lo_freq=24.2e9,
                 analysis_bandwidth=50e6,

                 **kwargs):



        Roach2Provider.__init__(self, **kwargs)



        self.roach2_hostname = roach2_hostname
        self._hf_lo_freq = hf_lo_freq
        self._analysis_bandwidth = analysis_bandwidth
        self.source_ip = str(source_ip)
        self.source_port = source_port
        self.source_mac = str(source_mac)
        self.dest_ip = str(dest_ip)
        self.dest_port = dest_port
        self.dest_mac = str(dest_mac)
        self.cfg_list = None
        self.daq_name = daq_name
        self.channel_tag = channel_tag
        self.central_freq = central_freq
        self.gain = gain
        self.configured=False
        self.calibrated=False
       # self.do_calibrations=do_adc_ogp_calibration



    def configure_roach(self, do_ogp_cal=False, do_adcif_cal=False, boffile='latest-build'):
#        if do_ogp_cal==True and do_adcif_cal==True:
#            self.calibrated=True

        if self.source_port != None:
            cfg_a = self.make_interface_config_dictionary(self.source_ip, self.source_port,self.dest_ip, self.dest_port, src_mac=self.source_mac, dest_mac=self.dest_mac)
            #cfg_b = self.make_interface_config_dictionary('192.168.10.101',4000,'192.168.10.64',4001,dest_mac='00:60:dd:44:91:e8',tag='b')

            self.cfg_list = [cfg_a]
            logger.info(type(self.cfg_list))
            ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=do_ogp_cal, do_adcif_cal=do_adcif_cal, ifcfg=self.cfg_list)
            self.configured=True
        else:
            logger.info('Configuring ROACH2 without specific IP settings')
            ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=do_ogp_cal, do_adcif_cal=do_adcif_cal)
            self.configured=True

        self.set_central_frequency(self.central_freq)
        self.set_gain(self.gain)


        return self.configured

    def get_ip_configuration(self):
        logger.info('source ip: {}, source port: {},  \n dest ip: {}, dest port: {}'.format(self.source_ip,self.source_port, self.dest_ip,self.dest_port))
        return 'source ip: {}, source port: {} \n dest ip: {}, dest port: {}'.format(self.source_ip,self.source_port, self.dest_ip,self.dest_port)

    def get_calibration_status(self):
        return self.calibrated

    def get_configuration_status(self):
        return self.configured

    def do_adc_ogp_calibration(self, **kwargs):

        logger.info('Calibrating ROACH2, this will take a while.... no news is good news.')

        logger.info('Doing adc an ogp calibration')
        ArtooDaq.calibrate_adc_ogp(self, **kwargs)
        self.calibrated=True

        return self.calibrated


    def is_running(self):
        to_return = False
        logger.info('Pinging ROACH2')
        response = os.system("ping -c 1 " + self.roach2_hostname)
        #and then check the response...
        if response == 0:
            logger.info('ROACH2 is switched on')
            to_return = True

            if not self.get_configuration_status:
                logger.info('ROACH2 is not configured')
            if not self.get_calibration_status:
                logger.info('Roach2 is not calibrated')
        else:
            self.configured=False
            self.calibrated=False

        return to_return







    def set_central_frequency(self, cf):
        logger.info('setting central frequency of channel {} to {}'.format(self.channel_tag, cf))
        cf = ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=self.channel_tag)
        self.central_freq = cf
        return cf

    def get_central_frequency(self):
        return self.central_freq

    def get_ddc_config(self):
        cfg = self.read_ddc_1st_config(tag=self.channel_tag)
        logger.info('Configuration information of 1st stage DDC is {}'.format(self.channel_tag, cfg['digital']))


    def set_gain(self, gain):
        if gain>-8 and gain <7.93:
            logger.info('setting gain of channel {} to {}'.format(self.channel_tag, gain))
            ArtooDaq.set_gain(self, gain, tag=self.channel_tag)
            return True
        else:
            logger.error('Only gain values between -8 and 7.93 are allowed')
            return False

    def set_fft_shift(self, shift, tag):
        logger.info('setting fft shift of channel {} to {}'.format(tag, shift))
        ArtooDaq.set_fft_shift(self, str(shift), tag=tag)

    def get_packets(self,n=1,dsoc_desc=None,close_soc=True):
        if dsoc_desc == None:
            dsoc_desc = (str(self.dest_ip),self.dest_port)
        try:
            logger.info('grabbing packets from {}'.format(dsoc_desc))
            pkts=ArtooDaq.grab_packets(self,n,dsoc_desc,close_soc)
            logger.info('Freq not time: {}'.format(pkts[0].freq_not_time))
            x = pkts[0].interpret_data()
            logger.info('first 10 entries are:')
            logger.info(x[0:10])
            return True
        except:
            logger.warning('cannot grab packets')
            return False


    def monitor(self,dsoc_desc=None,close_soc=True, tag='a'):
        if dsoc_desc == None:
            dsoc_desc = (str(self.dest_ip),self.dest_port)

        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self,2,dsoc_desc,close_soc)

        if pkts[0].freq_not_time==False:
            x = pkts[0].interpret_data()
            f = pkts[1].interpret_data()
        elif pkts[1].freq_not_time==False:
            x = pkts[1].interpret_data()
            f = pkts[0].interpret_data()
        plt.figure()
        plt.plot(np.linspace(self.central_freq*10**-6-50,self.central_freq*10**-6+50,np.shape(x)[0]),(np.fft.fft(x)))
        plt.plot(np.linspace(self.central_freq*10**-6-50,self.central_freq*10**-6+50,np.shape(x)[0]),f)
        plt.xlabel('frequency [MHz]')
        plt.savefig('/home/cclaesse/monitor/freq_plot.png')






#    def set_ip_configuration(self,
#                 source_ip = None,
#                 source_port = None,
#                 dest_ip = None,
#                 dest_port = None,
#                 dest_mac = None,
#                 **kwargs):
#
#        self.source_ip = str(source_ip)
#        self.source_port = source_port
#        self.dest_ip = str(dest_ip)
#        self.dest_port = dest_port
#        self.dest_mac = dest_mac
#        logger.info('New ip configuration set. Reconfiguring the ROACH2...')
#        self.configure_roach(**kwargs)
