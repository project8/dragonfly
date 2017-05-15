# -*- coding: utf-8 -*-
"""
Interface for controlling the roach2
"""


from __future__ import absolute_import

import logging
import os
import adc5g
import numpy as np
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
                 channel_a_config = None,
                 channel_b_config = None,
                 channel_c_config = None,

                 daq_name = None,
                 do_adc_ogp_calibration = False,
                 default_frequency = 800e6,
                 gain = 7.0,
                 fft_shift = '1101010101010',
                 monitor_target = None,
                 **kwargs):


        Roach2Provider.__init__(self, **kwargs)

        self.roach2_hostname = roach2_hostname
        self.monitor_target = monitor_target

        self.channel_a_config = channel_a_config
        self.channel_b_config = channel_b_config
        self.channel_c_config = channel_c_config

        self.freq_dict = {'a':None, 'b':None, 'c':None}
        self.block_dict = {'a': False, 'b': False, 'c':False}
        self.daq_name = daq_name
        self.default_frequency = default_frequency
        self.gain_dict = {'a':gain, 'b':gain, 'c':gain}
        self.fft_shift = fft_shift
        self.configured=False
        self.calibrated=False
        


    def _finish_configure(self, do_ogp_cal=False, do_adcif_cal=True, boffile=None):
        self.channel_list = []
        self.cfg_list = []
        # make list with interface dictionaries
        if self.channel_a_config != None:
            cfg_a = self.make_interface_config_dictionary(src_ip=self.channel_a_config['source_ip'], src_port=self.channel_a_config['source_port'], src_mac=self.channel_a_config['source_mac'], 
                                                          dest_ip=self.channel_a_config['dest_ip'], dest_port=self.channel_a_config['dest_port'], dest_mac=self.channel_a_config['dest_mac'], tag='a')
            self.cfg_list.append(cfg_a)
            self.channel_list.append('a')

        if self.channel_b_config != None:
            cfg_b = self.make_interface_config_dictionary(src_ip=self.channel_b_config['source_ip'], src_port=self.channel_b_config['source_port'], src_mac=self.channel_b_config['source_mac'],
                                                          dest_ip=self.channel_b_config['dest_ip'], dest_port=self.channel_b_config['dest_port'], dest_mac=self.channel_b_config['dest_mac'], tag='b')
            self.cfg_list.append(cfg_b)
            self.channel_list.append('b')

        if self.channel_c_config != None:
            cfg_c = self.make_interface_config_dictionary(src_ip=self.channel_c_config['source_ip'], src_port=self.channel_c_config['source_port'], src_mac=self.channel_c_config['source_mac'],
                                                          dest_ip=self.channel_c_config['dest_ip'], dest_port=self.channel_c_config['dest_port'], dest_mac=self.channel_c_config['dest_mac'], tag='c')
            self.cfg_list.append(cfg_c)
            self.channel_list.append('c')

        logger.info('Number of channels: {}'.format(len(self.channel_list)))


        ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=do_ogp_cal, do_adcif_cal=do_adcif_cal, ifcfg=self.cfg_list)
        self.configured=True

        if boffile!=None:
            self.do_adc_ogp_calibration()

        for s in self.channel_list:
            self.set_central_frequency(self.default_frequency, s)
            self.gain = (self.gain_dict[s], s)
            self.fft_shift_vector = (self.fft_shift, 'ab')
            self.fft_shift_vector = (self.fft_shift, 'cd')
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


    @property
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
        self.block_dict[channel]=True


    def unblock_channel(self, channel):
        self.block_dict[channel]=False


    @property
    def blocked_channels(self):
        bc = [i for i in self.block_dict.keys() if self.block_dict[i]==True]
        return bc


    def get_central_frequency(self, channel):
        return self.freq_dict[channel]


    def set_central_frequency(self, cf, channel):
        if self.block_dict[channel]==False:
            logger.info('setting central frequency of channel {} to {}'.format(channel, cf))
            cf = ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=channel)
            self.freq_dict[channel]=cf
            return cf
        else:
            raise core.exceptions.DriplineGenericDAQError('Channel {} is blocked'.format(channel))


    @property
    def all_central_frequencies(self):
        return self.freq_dict
            

    @property
    def gain(self):
        return self.gain_dict


    @gain.setter
    def gain(self, val):
        gain, channel= val
        if self.block_dict[channel]==False:
            if gain>-8 and gain <7.93:
                logger.info('setting gain of channel {} to {}'.format(channel, gain))
                ArtooDaq.set_gain(self, gain, tag=channel)
                self.gain_dict[channel] = gain
            else:
                raise core.exceptions.DriplineGenericDAQError('Only gains between -8 and 7.93 are allowed')
        else:
            raise core.exceptions.DriplineGenericDAQError('Channel {} is blocked'.format(channel))


    @property
    def fft_shift_vector(self):
        return self.fft_shift


    @fft_shift_vector.setter
    def fft_shift_vector(self, val):
        shift, tag = val
        self.fft_shift = shift
        logger.info('setting fft shift of channel {} to {}'.format(tag, shift))
        ArtooDaq.set_fft_shift(self, str(shift), tag=tag)



    @property
    def roach2_clock(self):
        board_clock = self.roach2.est_brd_clk()
        return board_clock


    def get_T_packets(self,dsoc_desc=None, channel='a', NPackets=10, mean=True, path=None):
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
        t = []
        for i in range(int(NPackets*2)):
            if pkts[i].freq_not_time==False:  
                x=pkts[i].interpret_data()
                t.append(x)
                p.append(np.abs(np.fft.fftshift(np.fft.fft(x)))/N)
        p = np.array(p)
        t = nparray(t)
        NPackets = np.shape(p)[0] 
        if mean == True:
            p = np.mean(p, axis = 0)
        if path==None:
            path=self.monitor_target
        np.save(path+'/T_packets_ft_channel'+channel+'_cf_'+str(cf)+'Hz_gain_'+str(gain)+'_N_'+str(NPackets), p)
        np.save(path+'/T_packets_channel'+channel+'_cf_'+str(cf)+'Hz_gain_'+str(gain)+'_N_'+str(NPackets), t)


    def get_F_packets(self,dsoc_desc=None, channel='a', NPackets=100, mean=True):
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

