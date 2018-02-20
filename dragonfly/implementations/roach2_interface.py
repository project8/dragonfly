# -*- coding: utf-8 -*-
"""
Interface for controlling the roach2
"""


from __future__ import absolute_import

import logging
import os
try:
    import adc5g
    import numpy as np
except ImportError:
    pass
import json
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
        self.fft_shift_vector = {'ab': fft_shift, 'cd': fft_shift}
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

        for channel in self.channel_list:
            self.set_central_frequency(channel, self.default_frequency)
            self.set_gain(channel, self.gain_dict[channel])

        self.set_fft_shift_vector('ab', self.fft_shift_vector['ab'])
        self.set_fft_shift_vector('cd', self.fft_shift_vector['cd'])
        return self.configured

    @property
    def calibration_status(self):
        return self.calibrated


    def do_adc_ogp_calibration(self, **kwargs):
        logger.info('Calibrating ROACH2, this will take a while.')
        logger.info('Doing adc ogp calibration')
        adc_dictionary = ArtooDaq.calibrate_adc_ogp(self, **kwargs)
        logger.info('ADC calibration returned: {}'.format(adc_dictionary))
        self.calibrated=True
        return self.calibrated


    @property
    def is_running(self):
        logger.info('Pinging ROACH2')
        response = os.system("ping -c 1 " + self.roach2_hostname)
        #and then check the response...
        if response == 0:
            logger.info('ROACH2 is switched on')
        else:
            self.configured=False
            self.calibrated=False

        return self.configured


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


    def set_central_frequency(self, channel, cf):
        if self.block_dict[channel]==False:
            if cf > 1550e6 or cf < 50e6:
                logger.error('Frequency out of allowed range: 50e6 - 1550e6 Hz')
                raise core.exceptions.DriplineGenericDAQError('Frequency out of allowed range')
            else:
                logger.info('setting central frequency of channel {} to {}'.format(channel, cf))
                cf = ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=channel)
                self.freq_dict[channel]=cf
                return cf
        else:
            logger.error('Channel {} is blocked'.format(channel))
            raise core.exceptions.DriplineGenericDAQError('Channel {} is blocked'.format(channel))


    @property
    def all_central_frequencies(self):
        return self.freq_dict


    @property
    def gain(self):
        return self.gain_dict


    def set_gain(self, channel, gain):
        """
        Method to set the gain of a channel. The gain is applied after the first down conversion step.
        """
        if self.block_dict[channel]==False:
            if gain>-8 and gain <7.93:
                logger.info('setting gain of channel {} to {}'.format(channel, gain))
                ArtooDaq.set_gain(self, gain, tag=channel)
                self.gain_dict[channel] = gain
            else:
                raise core.exceptions.DriplineGenericDAQError('Only gains between -8 and 7.93 are allowed')
        else:
            raise core.exceptions.DriplineGenericDAQError('Channel {} is blocked'.format(channel))


    def get_fft_shift_vector(self, tag):
        return self.fft_shift_vector[tag]


    def set_fft_shift_vector(self, tag, fft_shift):
        """
        Method to set the fft_shift. See set_fft_shift in r2daq for more details.
        """

        self.fft_shift_vector[tag] = fft_shift
        logger.info('setting fft shift of channel {} to {}'.format(tag, fft_shift))
        ArtooDaq.set_fft_shift(self, str(fft_shift), tag=tag)



    @property
    def roach2_clock(self):
        board_clock = self.roach2.est_brd_clk()
        return board_clock


    def get_T_packets(self, channel='a', NPackets=1, path=None):
        if channel=='a':
            dsoc_desc = (self.channel_a_config['dest_ip'],self.channel_a_config['dest_port'])
        elif channel=='b':
            dsoc_desc = (self.channel_b_config['dest_ip'],self.channel_b_config['dest_port'])
        elif channel=='c':
            dsoc_desc = (self.channel_c_config['dest_ip'],self.channel_c_config['dest_port'])
        else:
            raise ValueError('{} is not a valid channel tag'.format(channel))

        if path == None:
            path = self.monitor_target

        cf = self.freq_dict[channel]
        gain = self.gain_dict[channel]

        logger.info('grabbing {} packets from {}'.format(NPackets*2,dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets*2, dsoc_desc, True)
        p = []
        for i in range(int(NPackets*2)):
            if pkts[i].freq_not_time==False:
                x=pkts[i].interpret_data()
                p.extend(x)
        NPackets = len(p/4096)
        p = np.mean(np.array(p), axis = 0)

        filename = '{}/{}_T_packets_channel{}_cf_{}Hz.json'.format(path, NPackets, channel, str(cf))
        with open(filename, 'w') as outfile:
            json.dump(p.tolist(), outfile)



    def get_F_packets(self,dsoc_desc=None, channel='a', NPackets=10, path = None):
        if channel=='a':
            dsoc_desc = (self.channel_a_config['dest_ip'],self.channel_a_config['dest_port'])
        elif channel=='b':
            dsoc_desc = (self.channel_b_config['dest_ip'],self.channel_b_config['dest_port'])
        elif channel=='c':
            dsoc_desc = (self.channel_c_config['dest_ip'],self.channel_c_config['dest_port'])
        else:
            raise ValueError('{} is not a valid channel tag'.format(channel))

        if path == None:
            path = self.monitor_target

        cf = self.freq_dict[channel]
        gain = self.gain_dict[channel]

        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets*2, dsoc_desc, True)
        logger.info('cf={}'.format(cf))

        p = []
        for i in range(int(NPackets*2)):
            if pkts[i].freq_not_time==True:
                f=pkts[i].interpret_data()
                p.append(np.abs(f))
        NPackets = len(p)
        p = np.mean(np.array(p), axis = 0)

        filename = '{}/mean_of_{}_F_packets_channel{}_cf_{}Hz.json'.format(path, NPackets, channel, str(cf))
        with open(filename, 'w') as outfile:
            json.dump(p.tolist(), outfile)


    def get_raw_adc_data(self, path = None):
        if path == None:
            raise core.exceptions.DriplineGenericDAQError('No path specified')
       
        x = ArtooDaq._snap_per_core(self, zdok=0)
        x_all = x.flatten('C')

        filename = path
        with open(filename, 'w') as outfile:
            json.dump(x_all.tolist(), outfile)


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
