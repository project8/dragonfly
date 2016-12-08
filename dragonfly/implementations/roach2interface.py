# -*- coding: utf-8 -*-
"""
"""


from __future__ import absolute_import

# standard imports
import logging
#import uuid
#import signal
import os
import adc5g
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
                 source_ip_a = None,
                 source_port_a = None,
                 source_mac_a = None,
                 dest_ip_a = None,
                 dest_port_a = None,
                 dest_mac_a = None,
                 channel_tag_a = 'a',

                 source_ip_b = None,
                 source_port_b = None,
                 source_mac_b = None,
                 dest_ip_b = None,
                 dest_port_b = None,
                 dest_mac_b = None,
                 channel_tag_b = 'b',

                 source_ip_c = None,
                 source_port_c = None,
                 source_mac_c = None,
                 dest_ip_c = None,
                 dest_port_c = None,
                 dest_mac_c = None,
                 channel_tag_c = 'c',

		 Nchannels = 1,
		 daq_name = None,
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
        self.source_ip = str(source_ip_a)
        self.source_port = source_port_a
        self.source_mac = str(source_mac_a)
        self.dest_ip = str(dest_ip_a)
        self.dest_port = dest_port_a
        self.dest_mac = str(dest_mac_a)

	self.source_ip_b = str(source_ip_b)
        self.source_port_b = source_port_b
        self.source_mac_b = str(source_mac_b)
        self.dest_ip_b = str(dest_ip_b)
        self.dest_port_b = dest_port_b
        self.dest_mac_b = str(dest_mac_b)

	self.source_ip_c = str(source_ip_c)
        self.source_port_c = source_port_c
        self.source_mac_c = str(source_mac_c)
        self.dest_ip_c = str(dest_ip_c)
        self.dest_port_c = dest_port_c
        self.dest_mac_c = str(dest_mac_c)



	self.channel_list = []
        self.cfg_list = []
        self.daq_name = daq_name
        self.channel_tag = channel_tag_a
        self.central_freq = central_freq
        self.gain = gain
        self.configured=False
        self.calibrated=False
       # self.do_calibrations=do_adc_ogp_calibration



    def configure(self, do_ogp_cal=False, do_adcif_cal=True, boffile=None):
#        if do_ogp_cal==True and do_adcif_cal==True:
#            self.calibrated=True

        if self.source_port != None:
            cfg_a = self.make_interface_config_dictionary(self.source_ip, self.source_port,self.dest_ip, self.dest_port, src_mac=self.source_mac, dest_mac=self.dest_mac, tag='a')
	    self.cfg_list.append(cfg_a)
	    self.channel_list.append('a')

	else:
            logger.info('Configuring ROACH2 without specific IP settings')
            ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=do_ogp_cal, do_adcif_cal=do_adcif_cal)
            self.configured=False


	if self.source_port_b != None:
	    cfg_b = self.make_interface_config_dictionary(self.source_ip_b, self.source_port_b,self.dest_ip_b, self.dest_port_b, src_mac=self.source_mac_b, dest_mac=self.dest_mac_b, tag ='b')
	    self.cfg_list.append(cfg_b)
	    self.channel_list.append('b')
	if self.source_port_c != None:
	    cfg_c = self.make_interface_config_dictionary(self.source_ip_c, self.source_port_c,self.dest_ip_c, self.dest_port_c, src_mac=self.source_mac_c, dest_mac=self.dest_mac_c, tag ='c')
	    self.cfg_list.append(cfg_c)
	    self.channel_list.append('c')

        logger.info('Number of channels: {}'.format(np.shape(np.array(self.cfg_list))))


        ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=do_ogp_cal, do_adcif_cal=do_adcif_cal, ifcfg=self.cfg_list)
        self.configured=True

	for s in self.channel_list:
	    self.set_central_frequency(self.central_freq, channel=s)
	    self.set_gain(self.gain,channel=s)

        return self.configured


    def get_ip_configuration(self):
        logger.info('source ip: {}, source port: {},  \n dest ip: {}, dest port: {}'.format(self.source_ip,self.source_port, self.dest_ip,self.dest_port))
        return self.cfg_list

    def get_calibration_status(self):
        return self.calibrated

    def get_configuration_status(self):
        return self.configured

    def do_adc_ogp_calibration(self, **kwargs):

        logger.info('Calibrating ROACH2, this will take a while.... no news is good news.')

        logger.info('Doing adc ogp calibration')
        d = ArtooDaq.calibrate_adc_ogp(self, **kwargs)
        logger.info(d)
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







    def set_central_frequency(self, cf, channel='a'):
        logger.info('setting central frequency of channel {} to {}'.format(channel, cf))
        cf1 = ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=channel)
	if channel == 'b':
            self.central_freq_b = cf1
	elif channel =='c':
            self.central_freq_c = cf1
	else:
	    self.central_freq_a = cf1
	return cf1

    def get_central_frequency(self):
	#self.central_frequency = ArtooDaq.read_ddc_1st_config(self, tag=self.channel_tag)['f_c']
        return self.central_freq

    def get_ddc_config(self):
        cfg = self.read_ddc_1st_config(tag=self.channel_tag)
        logger.info('Configuration information of 1st stage DDC is {}'.format(self.channel_tag, cfg['digital']))


    def set_gain(self, gain, channel='a'):
        if gain>-8 and gain <7.93:
            logger.info('setting gain of channel {} to {}'.format(channel, gain))
            ArtooDaq.set_gain(self, gain, tag=channel)
            return True
        else:
            logger.error('Only gain values between -8 and 7.93 are allowed')
            return False

    def set_fft_shift(self, shift, tag):
        logger.info('setting fft shift of channel {} to {}'.format(tag, shift))
        ArtooDaq.set_fft_shift(self, str(shift), tag=tag)

    def get_packets(self,n=1,channel='a',close_soc=True):
        if channel == 'b':
            dsoc_desc = (str(self.dest_ip_b),self.dest_port_b)
	elif channel == 'c':
	    dsoc_desc = (str(self.dest_ip_c), self.dest_port_c)
	else:
	    dsoc_desc = (str(self.dest_ip), self.dest_port)
        try:
            logger.info('grabbing packets from {}'.format(dsoc_desc))
            pkts=ArtooDaq.grab_packets(self,n,dsoc_desc,close_soc)
            logger.info('Freq not time: {}'.format(pkts[0].freq_not_time))
            x = pkts[0].interpret_data()
            logger.info('first 10 entries are:')
            logger.info(x[0:10])
		
            #return True
        except:
            logger.warning('cannot grab packets')
            return False
        if_ids, digital_ids, pktnum = [], [], []
        for i in range(n):
            if_ids.append(pkts[i].if_id)
            digital_ids.append(pkts[i].digital_id)
	    pktnum.append(pkts[i].pkt_in_batch)
        logger.info(if_ids)
        logger.info(digital_ids)
	logger.info(pktnum)
        plt.figure()
        plt.plot(np.array(pktnum))
        plt.savefig('/home/cclaesse/monitor/ids.png')



    def monitor(self,dsoc_desc=None,close_soc=True, channel='a'):
        if channel=='a':
            dsoc_desc = (str(self.dest_ip),self.dest_port)
	    cf = self.central_freq_a
	elif channel=='b':
	    dsoc_desc = (str(self.dest_ip_b),self.dest_port_b)
	    cf = self.central_freq_b
	elif channel=='c':
	    dsoc_desc = (str(self.dest_ip_c),self.dest_port_c)
            cf = self.central_freq_c

	

        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self,2,dsoc_desc,close_soc)

        if pkts[0].freq_not_time==False:
            x = pkts[0].interpret_data()
            f = pkts[1].interpret_data()
        elif pkts[1].freq_not_time==False:
            x = pkts[1].interpret_data()
            f = pkts[0].interpret_data()

	n = np.shape(x)[0]
	logger.info('array length {}'.format(n))
	p = np.abs(np.fft.fftshift(np.fft.fft(x)))
	logger.info(x[0:10])
	logger.info(f[0:10])
	logger.info('cf={}'.format(cf))
	p = p/np.max(p) 	
	cf = cf*10**-6
	logger.info('max value in f packet: {}, shape of fft of signal {}'.format(np.max(np.abs), np.shape(p)))
        plt.close("all")
	plt.figure()
        plt.plot(np.linspace(cf-50,cf+50,np.shape(x)[0]),10.0*np.log10(p), color='b', label='fft(T-Packet')
	logger.info('cf={}, shape={}'.format(cf, np.shape(x)[0]))

	#plt.plot(np.linspace(cf-50,cf+50,np.shape(x)[0]),np.abs(p), color='b')
	plt.plot(np.linspace(cf-50,cf+50,np.shape(x)[0]),10.0*np.log10(np.abs(f)/np.max(np.abs(f))), color='g',label='F-Packet')
        #plt.plot(np.linspace(cf-50,cf+50,np.shape(x)[0]),np.abs(f), color='g')
	plt.xlabel('frequency [MHz]')
	plt.ylabel('relativ amplitude [dB]')
	plt.legend()
	plt.title(channel)
        plt.savefig('/home/cclaesse/monitor/freq_plot.png')
	logger.info('file saved')


    def calibrate_manually(self, gain1=0.0, gain2=0.42, gain3=0.42, gain4=1.55, off1=3.14, off2=-0.39, off3=2.75, off4=-1.18):
	adc5g.set_spi_gain(self.roach2,0, 1, gain1)
	adc5g.set_spi_gain(self.roach2,0, 2, gain2)
	adc5g.set_spi_gain(self.roach2,0, 3, gain3)
	adc5g.set_spi_gain(self.roach2,0, 4, gain4)
	adc5g.set_spi_offset(self.roach2,0, 1, off1)
	adc5g.set_spi_offset(self.roach2,0, 2, off2)
	adc5g.set_spi_offset(self.roach2,0, 3, off3)
	adc5g.set_spi_offset(self.roach2,0, 4, off4)

	return True
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
