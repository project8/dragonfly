# -*- coding: utf-8 -*-
"""
"""


from __future__ import absolute_import

import logging
import os
import adc5g
import numpy as np
#import time
from dripline import core


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
class Roach2Interface(Roach2Provider):
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
                 monitor_target = None,
                 **kwargs):


        Roach2Provider.__init__(self, **kwargs)


        self.roach2_hostname = roach2_hostname
        self.monitor_target = monitor_target

	#channel a
        self.source_ip = str(source_ip_a)
        self.source_port = source_port_a
        self.source_mac = str(source_mac_a)
        self.dest_ip = str(dest_ip_a)
        self.dest_port = dest_port_a
        self.dest_mac = str(dest_mac_a)

	#channel b
        self.source_ip_b = str(source_ip_b)
        self.source_port_b = source_port_b
        self.source_mac_b = str(source_mac_b)
        self.dest_ip_b = str(dest_ip_b)
        self.dest_port_b = dest_port_b
        self.dest_mac_b = str(dest_mac_b)

	#channel c
        self.source_ip_c = str(source_ip_c)
        self.source_port_c = source_port_c
        self.source_mac_c = str(source_mac_c)
        self.dest_ip_c = str(dest_ip_c)
        self.dest_port_c = dest_port_c
        self.dest_mac_c = str(dest_mac_c)


        self.channel_list = []
        self.freq_dict = {'a':None, 'b':None, 'c':None}
        self.block_dict = {'a': False, 'b': False, 'c':False}
        self.cfg_list = []
        self.daq_name = daq_name
        self.central_freq = central_freq
        self.gain_dict = {'a':gain, 'b':gain, 'c':gain}
        self.configured=False
        self.calibrated=False
        


    def configure(self, do_ogp_cal=False, do_adcif_cal=True, boffile=None):
        self.channel_list = []
        self.cfg_list = []
        # make list with interface dictionaries
        if self.source_port != None:
            cfg_a = self.make_interface_config_dictionary(self.source_ip, self.source_port,self.dest_ip, self.dest_port, src_mac=self.source_mac, dest_mac=self.dest_mac, tag='a')
            self.cfg_list.append(cfg_a)
            self.channel_list.append('a')

        if self.source_port_b != None:
            cfg_b = self.make_interface_config_dictionary(self.source_ip_b, self.source_port_b,self.dest_ip_b, self.dest_port_b, src_mac=self.source_mac_b, dest_mac=self.dest_mac_b, tag ='b')
            self.cfg_list.append(cfg_b)
            self.channel_list.append('b')

        if self.source_port_c != None:
            cfg_c = self.make_interface_config_dictionary(self.source_ip_c, self.source_port_c,self.dest_ip_c, self.dest_port_c, src_mac=self.source_mac_c, dest_mac=self.dest_mac_c, tag ='c')
            self.cfg_list.append(cfg_c)
            self.channel_list.append('c')

        logger.info('Number of channels: {}'.format(len(self.channel_list)))


        ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=do_ogp_cal, do_adcif_cal=do_adcif_cal, ifcfg=self.cfg_list)
        self.configured=True

        if boffile!=None:
            self.do_adc_ogp_calibration()

        for s in self.channel_list:
            self.set_central_frequency(800.0e6, channel=s)
            self.set_gain(self.gain_dict[s],channel=s)
            self.set_fft_shift('1101010101010', tag='ab')
            self.set_fft_shift('1101010101010', tag='cd')
        return self.configured


    def get_calibration_status(self):
        return self.calibrated


    def get_configuration_status(self):
        return self.configured


    def do_adc_ogp_calibration(self, **kwargs):
        logger.info('Calibrating ROACH2, this will take a while.')
        logger.info('Doing adc ogp calibration')
        adc_dictionary = ArtooDaq.calibrate_adc_ogp(self, **kwargs)
        logger.info(adc_dictionary)
        self.calibrated=True
        return self.calibrated


    def is_running(self):
        logger.info('Pinging ROACH2')
        response = os.system("ping -c 1 " + self.roach2_hostname)
        #and then check the response...
        if response == 0:
            logger.info('ROACH2 is switched on')

            if not self.get_configuration_status:
                logger.info('ROACH2 is not configured')
            if not self.get_calibration_status:
                logger.info('Roach2 is not calibrated')
        else:
            self.configured=False
            self.calibrated=False

        return self.calibrated


    def block_channel(self, channel):
        if self.block_dict.has_key(channel)==False:
            logger.info('{} is not a valid channel label'.format(channel))
            return False
        self.block_dict[channel]=True
        return self.block_dict


    def unblock_channel(self, channel):
        if self.block_dict.has_key(channel)==False:
            logger.info('{} is not a valid channel label'.format(channel))
            return False
        self.block_dict[channel]=False
        return self.block_dict


    def set_central_frequency(self, cf, channel='a'):
        if self.block_dict[channel]==False:
            logger.info('setting central frequency of channel {} to {}'.format(channel, cf))
            try:
                cf = ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=channel)
                self.freq_dict[channel]=cf
                return cf
            except:
                logger.error('setting central frequency failed')
                self.freq_dict[channel]=None
                self.calibrated = False
                self.configured = False
                raise core.exceptions.DriplineGenericDAQError('Setting central frequency failed in roach2_service')
        else:
            logger.error('Channel blocked')
            return False    


    def get_central_frequency(self, channel='a'):
        return self.freq_dict[channel]


    def get_all_central_frequencies(self):
        return self.freq_dict
            

    def set_gain(self, gain, channel='a'):
        if gain>-8 and gain <7.93:
            logger.info('setting gain of channel {} to {}'.format(channel, gain))
            ArtooDaq.set_gain(self, gain, tag=channel)
            self.gain_dict[channel] = gain
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
        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self,n,dsoc_desc,close_soc)
        logger.info('Freq not time: {}'.format(pkts[0].freq_not_time))
        x = pkts[0].interpret_data()
        logger.info('first 10 entries are:')
        logger.info(x[0:10])


    def get_roach2_clock(self):
        a = self.roach2.est_brd_clk()
        logger.info('{}'.format(a))
        return a


    def get_T_packet(self,dsoc_desc=None,close_soc=True, channel='a'):
        if channel=='a':
            dsoc_desc = (str(self.dest_ip),self.dest_port)
        elif channel=='b':
            dsoc_desc = (str(self.dest_ip_b),self.dest_port_b)
        elif channel=='c':
            dsoc_desc = (str(self.dest_ip_c),self.dest_port_c)

        cf = self.freq_dict[channel]
        gain = self.gain_dict[channel]

        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self,2,dsoc_desc,close_soc)

        if pkts[0].freq_not_time==False:
            x = pkts[0].interpret_data()
            f = pkts[1].interpret_data()
            pkt_id=pkts[0].pkt_in_batch
        elif pkts[1].freq_not_time==False:
            x = pkts[1].interpret_data()
            f = pkts[0].interpret_data()
            pkt_id=pkts[1].pkt_in_batch

        p = np.abs(np.fft.fftshift(np.fft.fft(x)))/4096
        logger.info('first 10 entries in time domain array: ')
        logger.info(x[0:10])
        gain = self.gain_dict[channel]
        np.save(self.monitor_target+'/T_packet_channel_'+channel+'_cf_'+str(cf)+'Hz_gain_'+str(gain), p)
        np.save(self.monitor_target+'/time_domain_T_packet_channel_'+channel+'_cf_'+str(cf)+'Hz_gain_'+str(gain), x)


    def get_F_packet(self,dsoc_desc=None,close_soc=True, channel='a'):
        if channel=='a':
            dsoc_desc = (str(self.dest_ip),self.dest_port)
        elif channel=='b':
            dsoc_desc = (str(self.dest_ip_b),self.dest_port_b)
        elif channel=='c':
            dsoc_desc = (str(self.dest_ip_c),self.dest_port_c)

        cf = self.freq_dict[channel]
        gain = self.gain_dict[channel]

        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self,2,dsoc_desc,close_soc)

        if pkts[0].freq_not_time==False:
            x = pkts[0].interpret_data()
            f = pkts[1].interpret_data()
            pkt_id=pkts[1].pkt_in_batch

        elif pkts[1].freq_not_time==False:
            x = pkts[1].interpret_data()
            f = pkts[0].interpret_data()
            pkt_id=pkts[0].pkt_in_batch

        logger.info('first 10 entries in frequency domain array: ')
        logger.info(f[0:10])
        logger.info('cf={}'.format(cf))
        np.save(self.monitor_target+'/F_packet_channel_'+channel+'_cf_'+cf+'Hz_gain_'+str(gain), f)
        logger.info('file saved to {}'.format(self.monitor_target))


    def get_multiple_T_packets(self,dsoc_desc=None, channel='a', NPackets=10, mean=True, path=None):
        if channel=='a':
            dsoc_desc = (str(self.dest_ip),self.dest_port)
        elif channel=='b':
            dsoc_desc = (str(self.dest_ip_b),self.dest_port_b)
        elif channel=='c':
            dsoc_desc = (str(self.dest_ip_c),self.dest_port_c)

        cf = self.freq_dict[channel]
        gain = self.gain_dict[channel]

        logger.info('grabbing {} packets from {}'.format(NPackets*2,dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets*2, dsoc_desc, True)
        logger.info('cf={}'.format(cf))
        N = 4096
        p = []
        for i in range(int(NPackets*2)):
            if pkts[i].freq_not_time==False:  
                x=pkts[i].interpret_data()
                p.append(np.abs(np.fft.fftshift(np.fft.fft(x)))/N)
        p = np.array(p)
        NPackets = np.shape(p)[0] 
        if mean == True:
            p = np.mean(p, axis = 0)
        if path==None:
            path=self.monitor_target
        np.save(path+'/T_packets_channel'+channel+'_cf_'+str(cf)+'Hz_gain_'+str(gain)+'_N_'+str(NPackets), p)


    def get_multiple_F_packets(self,dsoc_desc=None, channel='a', NPackets=100, mean=True):
        if channel=='a':
            dsoc_desc = (str(self.dest_ip),self.dest_port)
        elif channel=='b':
            dsoc_desc = (str(self.dest_ip_b),self.dest_port_b)
        elif channel=='c':
            dsoc_desc = (str(self.dest_ip_c),self.dest_port_c)

        cf = self.freq_dict[channel]
        gain = self.gain_dict[channel]

        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets*2, dsoc_desc, True)
        logger.info('cf={}'.format(cf))
        N = 4096
        p = []
        for i in range(int(NPackets*2)):
            if pkts[i].freq_not_time==True:
                f=pkts[i].interpret_data()
                p.append(np.abs(f))
        p = np.array(p)
        if mean == True:
            p = np.mean(p, axis = 0)
        np.save(self.monitor_target+'/F_packets_channel_'+channel+'_cf_'+str(cf)+'Hz_gain_'+str(gain), p)


    def get_raw_adc_data(self, count=0, N=1, mean = True):
        p = []
        for i in range(N):
            x = ArtooDaq._snap_per_core(self, zdok=0)
            x_all = x.flatten('C')
            logger.info('shape x is {} shape x_all is {}'.format(np.shape(x), np.shape(x_all)))
            x_all = x_all/128.0*0.25
            for i in range(16):
                p.append(np.abs(np.fft.fftshift(np.fft.fft(x_all[i*16384:(i+1)*16384])))/16384)
        p = np.array(p)
        if mean == True:
            p = np.mean(p, axis = 0)
        logger.info('shape of saved array is: {}'.format(np.shape(p)))
        np.save(self.monitor_target+'/raw_adc'+str(count), p)
	logger.info('Raw data saved to {}'.format(self.monitor_target+'/raw_adc'+str(count)+'.npy'))


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

