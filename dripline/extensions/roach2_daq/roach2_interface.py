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



__all__.append('Roach2Interface')
class Roach2Interface(ArtooDaq, core.Endpoint):
    
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
                 **kwargs):


        core.Endpoint.__init__(self, **kwargs)

        self.roach2_hostname = roach2_hostname

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



    def _finish_configure(self, boffile=None, **kwargs):
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

        ArtooDaq.__init__(self, self.roach2_hostname, boffile=boffile, do_ogp_cal=False, do_adcif_cal=True, ifcfg=self.cfg_list)
        self.configured = True

        for channel in self.channel_list:
            self.set_central_frequency(channel, self.default_frequency)
            self.set_gain(channel, self.gain_dict[channel])

        self.set_fft_shift_vector('ab', self.fft_shift_vector['ab'])
        self.set_fft_shift_vector('cd', self.fft_shift_vector['cd'])
        return self.configured

    @property
    def calibration_status(self):
        return self.calibrated


    def do_adc_calibration(self):
        logger.info('Calibrating ROACH2, this will take a while.')
        logger.info('Doing adc ogp calibration')
        adc_cal_values = ArtooDaq.calibrate_adc_ogp(self, oiter=5, giter=5)
        logger.info('ADC calibration returned: {}'.format(adc_cal_values))
        for k in adc_cal_values.keys():
            if adc_cal_values[k] is None:
                self.calibrated = False
                logger.critical('ADC calibration failed')
                raise core.ThrowReply('DriplineGenericDAQError','ADC calibration failed')
        self.calibrated = True


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
        print("\nDEBUG: is_running pnt 1 reached. \n")
        return self.configured


    def block_channel(self, channel):
        print("\nDEBUG: reached block_channel pnt 1.\n")
        self.block_dict[channel]=True


    def unblock_channel(self, channel):
        self.block_dict[channel]=False


    @property
    def blocked_channels(self):
        bc = [i for i in self.block_dict.keys() if self.block_dict[i]==True]
        return ''.join(i for i in bc)


    def get_central_frequency(self, channel):
        return self.freq_dict[channel]


    def set_central_frequency(self, channel, cf):
        if self.block_dict[channel]==False:
            if cf > 1550e6 or cf < 50e6:
                logger.error('Frequency out of allowed range: 50e6 - 1550e6 Hz')
                raise core.ThrowReply('DriplineGenericDAQError','Frequency out of allowed range')
            else:
                logger.info('setting central frequency of channel {} to {}'.format(channel, cf))
                cf = ArtooDaq.tune_ddc_1st_to_freq(self, cf, tag=channel)
                self.freq_dict[channel]=cf
                return cf
        else:
            logger.error('Channel {} is blocked'.format(channel))
            raise core.ThrowReply('DriplineGenericDAQError','Channel {} is blocked'.format(channel))


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
                raise core.ThrowReply('DriplineGenericDAQError','Only gains between -8 and 7.93 are allowed')
        else:
            raise core.ThrowReply('DriplineGenericDAQError','Channel {} is blocked'.format(channel))


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


    def get_packets(self, channel='a', NPackets=1, filename=None):
        if channel=='a':
            dsoc_desc = (self.channel_a_config['dest_ip'],self.channel_a_config['dest_port'])
        elif channel=='b':
            dsoc_desc = (self.channel_b_config['dest_ip'],self.channel_b_config['dest_port'])
        elif channel=='c':
            dsoc_desc = (self.channel_c_config['dest_ip'],self.channel_c_config['dest_port'])
        else:
            raise ValueError('{} is not a valid channel tag'.format(channel))

        logger.info('grabbing {} packets from {}'.format(NPackets,dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets, dsoc_desc, True)
        logger.info('pkt in batch: {}, digital id: {}, if id: {}'.format(pkts[0].pkt_in_batch, pkts[0].digital_id, pkts[0].if_id))
        p = {}

        for i in range(NPackets):
            if pkts[i].freq_not_time==False:
                packet_type = 'time'
            else:
                packet_type='frequency'
            x=np.complex128(pkts[i].interpret_data())
            p[i] = {'real': list(x.real), 'imaginary': list(x.imag), 'type': packet_type, 'pkt_in_batch': int(pkts[i].pkt_in_batch)}

        if filename is not None:
            with open(filename, 'w') as outfile:
                json.dump(p, outfile)
        else:
            return p

    def get_T_packets(self, channel='a', NPackets=1, filename=None):
        if channel=='a':
            dsoc_desc = (self.channel_a_config['dest_ip'],self.channel_a_config['dest_port'])
        elif channel=='b':
            dsoc_desc = (self.channel_b_config['dest_ip'],self.channel_b_config['dest_port'])
        elif channel=='c':
            dsoc_desc = (self.channel_c_config['dest_ip'],self.channel_c_config['dest_port'])
        else:
            raise ValueError('{} is not a valid channel tag'.format(channel))


        logger.info('grabbing {} packets from {}'.format(NPackets*2,dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets*2, dsoc_desc, True)
        p = {}
        ipacket = 0
        for i in range(NPackets*2):
            if pkts[i].freq_not_time==False:
                x=np.complex128(pkts[i].interpret_data())
                p[ipacket] = {'real': list(x.real), 'imaginary': list(x.imag)}
                ipacket+=1

        if filename is not None:
            with open(filename, 'w') as outfile:
                json.dump(p, outfile)
        else:
            return p



    def get_F_packets(self,dsoc_desc=None, channel='a', NPackets=10, filename = None):
        if channel=='a':
            dsoc_desc = (self.channel_a_config['dest_ip'],self.channel_a_config['dest_port'])
        elif channel=='b':
            dsoc_desc = (self.channel_b_config['dest_ip'],self.channel_b_config['dest_port'])
        elif channel=='c':
            dsoc_desc = (self.channel_c_config['dest_ip'],self.channel_c_config['dest_port'])
        else:
            raise ValueError('{} is not a valid channel tag'.format(channel))


        logger.info('grabbing packets from {}'.format(dsoc_desc))
        pkts=ArtooDaq.grab_packets(self, NPackets*2, dsoc_desc, True)

        p = {}
        ipacket = 0
        for i in range(NPackets*2):
            if pkts[i].freq_not_time==True:
                f=np.complex128(pkts[i].interpret_data())
                p[ipacket] = {'real': list(f.real), 'imaginary': list(f.imag)}
                ipacket+=1

        if filename is not None:
            with open(filename, 'w') as outfile:
                json.dump(p, outfile)
        else:
            return p


    def get_raw_adc_data(self, NSnaps = 1, filename = None):
        x_all = []
        for i in range(NSnaps):
            x = ArtooDaq._snap_per_core(self, zdok=0)
            x_all.extend(x.flatten('C'))
        logger.info('raw adc samples: {}'.format(len(x_all)))
        if filename is not None:
            logger.info('Saving raw adc data to {}'.format(filename))
            with open(filename, 'w') as outfile:
                json.dump(map(int,x_all), outfile)
        else:
            return list(x_all)



    def calibrate_with_2016_values(self):
        """
        Calibrates the ADC cores with values from a working calibration in 2016
        """
        self.calibrate_manually(gain1=0.0, gain2=0.42, gain3=0.42, gain4=1.55, offset1=3.14, offset2=-0.39, offset3=2.75, offset4=-1.18, phase1=None, phase2=None, phase3=None, phase4=None)


    def calibrate_manually(self, gain1=None, gain2=None, gain3=None, gain4=None, offset1=None, offset2=None, offset3=None, offset4=None, phase1=None, phase2=None, phase3=None, phase4=None):
        """
        Calibrate the ADC cores manually
        """
        if gain1 is not None:
            adc5g.set_spi_gain(self.roach2,0, 1, gain1)
        if gain2 is not None:
            adc5g.set_spi_gain(self.roach2,0, 2, gain2)
        if gain3 is not None:
            adc5g.set_spi_gain(self.roach2,0, 3, gain3)
        if gain4 is not None:
            adc5g.set_spi_gain(self.roach2,0, 4, gain4)

        if offset1 is not None:
            adc5g.set_spi_offset(self.roach2,0, 1, offset1)
        if offset2 is not None:
            adc5g.set_spi_offset(self.roach2,0, 2, offset2)
        if offset3 is not None:
            adc5g.set_spi_offset(self.roach2,0, 3, offset3)
        if offset4 is not None:
            adc5g.set_spi_offset(self.roach2,0, 4, offset4)

        if phase1 is not None:
            adc5g.set_spi_phase(self.roach2, 0, 1, phase1)
        if phase2 is not None:
            adc5g.set_spi_phase(self.roach2, 0, 2, phase2)
        if phase3 is not None:
            adc5g.set_spi_phase(self.roach2, 0, 3, phase3)
        if phase4 is not None:
            adc5g.set_spi_phase(self.roach2, 0, 4, phase4)


    @property
    def adc_calibration_values(self):
        calibration_values = {}
        calibration_values['gain1'] = adc5g.get_spi_gain(self.roach2, 0, 1)
        calibration_values['gain2'] = adc5g.get_spi_gain(self.roach2, 0, 2)
        calibration_values['gain3'] = adc5g.get_spi_gain(self.roach2, 0, 3)
        calibration_values['gain4'] = adc5g.get_spi_gain(self.roach2, 0, 4)
        calibration_values['offset1'] = adc5g.get_spi_offset(self.roach2, 0, 1)
        calibration_values['offset2'] = adc5g.get_spi_offset(self.roach2, 0, 2)
        calibration_values['offset3'] = adc5g.get_spi_offset(self.roach2, 0, 3)
        calibration_values['offset4'] = adc5g.get_spi_offset(self.roach2, 0, 4)
        calibration_values['phase1'] = adc5g.get_spi_phase(self.roach2, 0, 1)
        calibration_values['phase2'] = adc5g.get_spi_phase(self.roach2, 0, 2)
        calibration_values['phase3'] = adc5g.get_spi_phase(self.roach2, 0, 3)
        calibration_values['phase4'] = adc5g.get_spi_phase(self.roach2, 0, 4)
        return calibration_values
