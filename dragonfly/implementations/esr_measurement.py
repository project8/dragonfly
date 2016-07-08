from __future__ import absolute_import
__all__ = []

import numpy
import logging

from dripline import core

logger = logging.getLogger(__name__)


def lockin_result_to_array(result):
    return numpy.array(result.replace('\x00','').split(';'), dtype=float)

__all__.append('ESR_Measurement')
#@fancy_doc
class ESR_Measurement(core.Endpoint):
    """
        Operate the ESR system
    """
    def __init__(self,
                 lockin_n_points,
                 lockin_sampling_interval,
                 lockin_trigger,
                 lockin_curve_mask,
                 lockin_srq_mask,
                 lockin_osc_amp,
                 lockin_osc_freq,
                 lockin_ac_gain,
                 lockin_sensitivity,
                 lockin_time_constant,
                 hf_start_freq,
                 hf_stop_freq,
                 hf_power,
                 hf_n_sweep_points,
                 hf_dwell_time,
                 **kwargs):
        core.Endpoint.__init__(self,**kwargs)
        # Settings for lockin and sweeper
	self.lockin_n_points = lockin_n_points
	self.lockin_sampling_interval = lockin_sampling_interval
	self.lockin_trigger = lockin_trigger
	self.lockin_curve_mask = lockin_curve_mask
	self.lockin_srq_mask = lockin_srq_mask
	self.lockin_osc_amp = lockin_osc_amp
	self.lockin_osc_freq = lockin_osc_freq
	self.lockin_ac_gain = lockin_ac_gain
	self.lockin_sensitivity = lockin_sensitivity
	self.lockin_time_constant = lockin_time_constant
	self.hf_start_freq = float(hf_start_freq)
	self.hf_stop_freq = float(hf_stop_freq)
	self.hf_power = hf_power
	self.hf_n_sweep_points = hf_n_sweep_points
	self.hf_dwell_time = hf_dwell_time
        # Constants and analysis parameters
        self.width = 10.0e6 #resonance width in Hz, for a gaussian filter it is sigma, for a lorentzian it is FWMH
        self.electron_cyclotron_frequency = 1.758820024e11 # rad s^-1 T^-1
        self.esr_g_factor = 2.0026
        # Output storage
        self.data_dict = {}
        
    # Configure instruments to default settings
    def configure_instruments(self):
        # dsp_lockin_7265 controls
        self.set_ept('lockin_n_points', self.lockin_n_points)
        self.set_ept('lockin_sampling_interval', self.lockin_sampling_interval)
        self.set_ept('lockin_trigger', self.lockin_trigger)
        self.set_ept('lockin_curve_mask', self.lockin_curve_mask)
        self.set_ept('lockin_srq_mask', self.lockin_srq_mask)
        self.set_ept('lockin_osc_amp', self.lockin_osc_amp)
        self.set_ept('lockin_osc_freq', self.lockin_osc_freq)
        #self.set_ept('lockin_ac_gain', self.lockin_ac_gain)
        self.set_ept('lockin_sensitivity', self.lockin_sensitivity)
        self.set_ept('lockin_time_constant', self.lockin_time_constant)
        # sweeper controls
        self.set_ept('hf_output_status', 0)
        self.set_ept('hf_start_freq', self.hf_start_freq)
        self.set_ept('hf_stop_freq', self.hf_stop_freq)
        self.set_ept('hf_power', self.hf_power)
        self.set_ept('hf_n_sweep_points', self.hf_n_sweep_points)
        self.set_ept('hf_dwell_time', self.hf_dwell_time)
        # relays
        for i in range(1, 6):
            self.set_ept('esr_coil_{}_switch_status'.format(i), 0)

    def single_measure(self, coilnum):
        self.set_ept('esr_coil_{}_switch_status'.format(coilnum), 1)
        self.set_ept('hf_output_status', 1)
        self.empty_get_ept('lockin_take_data')
        # HF sweep takes 60 sec
        while True:
            status = self.raw_get_ept('lockin_curve_status')[0]
            logger.info(status)
            if status.split(',',1)[0] == 'done':
                break
        self.set_ept('hf_output_status', 0)
        self.set_ept('esr_coil_{}_switch_status'.format(coilnum), 0)

        # Get the lockin data
        data = {}
        data['sweep_out'] = lockin_result_to_array(self.set_ept('lockin_grab_data', 'adc')[0])
        data['lockin_x_data'] = lockin_result_to_array(self.set_ept('lockin_grab_data', 'x')[0])
        data['lockin_y_data'] = lockin_result_to_array(self.set_ept('lockin_grab_data', 'y')[0])
        ten_volts = 10.0
        frequency_span = self.hf_stop_freq - self.hf_start_freq
        data['frequency'] = self.hf_start_freq + frequency_span * data['sweep_out']/ten_volts
        data['amplitude'] = data['lockin_x_data'] + 1j*data['lockin_y_data']

        # Weiner filter and analysis
        filter_data = WeinerFilter(data['frequency'],data['amplitude'],self.width,'lorentzian')
            #TODO a fit would be more appropriate to get uncertainty
        max_freq_index = numpy.argmax(filter_data['result'])
        res_freq = filter_data['freqs'][max_freq_index]
        b_field=4.*numpy.pi*res_freq/(self.esr_g_factor*self.electron_cyclotron_frequency)
        self.data_dict[coilnum] = { 'field' : b_field,
                                    'res_freq' : res_freq,
                                    'raw_data' : { 'frequency' : data['frequency'],
                                                   'amplitude' : data['amplitude'] },
                                    'filtered_data' : filter_data }
        logger.info("Coil #{} result: field = {}, res_freq = {}".format(coilnum,b_field,res_freq))

        return b_field


    def run_scan(self):
        self.configure_instruments()
        for i in range(1, 6):
            self.single_measure(i)
        logger.info(self.data_dict)
        return [self.data_dict[i]['field'] for i in range(1,6)]


    def empty_get_ept(self, endptname):
        request_message = core.RequestMessage(msgop=core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)

    def get_ept(self, endptname):
        request_message = core.RequestMessage(msgop=core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)
        ret_rep=''
        if a_result.retcode != 0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
        else:
            ret_val = a_result.payload['value_cal']
        return ret_val,ret_rep

    def raw_get_ept(self, endptname):
        request_message = core.RequestMessage(msgop=core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)
        if a_result.retcode == 0 :
            return a_result.payload['values']
        else:
            return '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)

    def set_ept(self,endptname,val):
        request_message = core.RequestMessage(msgop=core.OP_SET,
                                              payload={'values':[val]})
        a_result=self.portal.send_request(request=request_message,target=endptname)
        if a_result.retcode != 0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
            logger.alert("got error "+ret_rep)
        else:
            if 'values' in a_result.payload:
                ret_val = a_result.payload['values']
            elif 'value_cal' in a_result.payload:
                ret_val = a_result.payload['value_cal']
            else:
                logger.info("return payload is {}".format(a_result.payload))
                ret_val = a_result.payload
        return ret_val


def WeinerFilter(freq_data, amp_data, width, target='gaussian'):
    logger.warning('doing filter on target: {}'.format(target))
    data = zip(freq_data, amp_data)
    data.sort()
    f,v= zip(*data)
    frequencies = numpy.array(f, dtype=float)
    voltages = numpy.array(v, dtype=complex)
    x1 = (frequencies - frequencies[0])
    x2 = (frequencies - frequencies[-1])
    gderiv1 = x1 * numpy.exp(-x1**2 / 2. / width**2) / width
    gderiv2 = x2 * numpy.exp(-x2**2 / 2. / width**2) / width
    lderiv1 = -16. * x1 * width / (numpy.pi * (4*x1**2 + width**2))
    lderiv2 = -16. * x2 * width / (numpy.pi * (4*x2**2 + width**2))
    targets = {}
    targets['gaussian'] = numpy.concatenate((gderiv1[:len(gderiv1)/2], gderiv2[len(gderiv2)/2:]))
    targets['lorentzian'] = numpy.concatenate((lderiv1[:len(lderiv1)/2], lderiv2[len(lderiv2)/2:]))
    target_signal = targets[target]
    if not sum(target_signal != 0):
        raise ValueError("target signal identically 0, did you give width in Hz?")
    target_fft = numpy.fft.fft(target_signal)
    data_fft = numpy.fft.fft(voltages)
    data_fft[0] = 0
    filtered = numpy.fft.ifft(data_fft * target_fft)
    return {'freqs': frequencies,
            'result': numpy.abs(filtered),
            'target': target_signal
           }
