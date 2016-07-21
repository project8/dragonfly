from __future__ import absolute_import
__all__ = []

import numpy
import logging
from datetime import datetime
from ROOT import TFile, TTree, gROOT, AddressOf

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
        self.electron_cyclotron_frequency = 1.758820024e11 # rad s^-1 T^-1
        self.esr_g_factor = 2.0026
        # Output storage
        self.data_dict = {}
        self.root_setup()

    # Configure instruments to default settings
    def configure_instruments(self):
        # dsp_lockin_7265 controls
        self.check_ept('lockin_n_points', self.lockin_n_points)
        self.check_ept('lockin_sampling_interval', self.lockin_sampling_interval)
        self.check_ept('lockin_trigger', self.lockin_trigger)
        self.check_ept('lockin_curve_mask', self.lockin_curve_mask)
        self.check_ept('lockin_srq_mask', self.lockin_srq_mask)
        self.check_ept('lockin_osc_amp', self.lockin_osc_amp)
        self.check_ept('lockin_osc_freq', self.lockin_osc_freq)
        #self.check_ept('lockin_ac_gain', self.lockin_ac_gain)
        self.check_ept('lockin_sensitivity', self.lockin_sensitivity)
        self.check_ept('lockin_time_constant', self.lockin_time_constant)
        # sweeper controls
        while True:
            err_msg = self.raw_get_ept('hf_error_check')
            if err_msg == '+0,"No error"':
                break
            logger.warning("Clearing sweeper error queue: {}".format(err_msg))
        self.check_ept('hf_output_status', 0)
        self.check_ept('hf_freq_mode','LIST')
        self.check_ept('hf_start_freq', self.hf_start_freq)
        self.check_ept('hf_stop_freq', self.hf_stop_freq)
        self.check_ept('hf_power', self.hf_power)
        self.check_ept('hf_n_sweep_points', self.hf_n_sweep_points)
        self.check_ept('hf_dwell_time', self.hf_dwell_time)
        err_msg = self.raw_get_ept('hf_error_check')
        if err_msg != '+0,"No error"':
            raise core.exceptions.DriplineHardwareError("Sweeper error: {}".format(err_msg))
        # relays
        self.check_ept('esr_tickler_switch', 1)
        for i in range(1, 6):
            self.check_ept('esr_coil_{}_switch_status'.format(i), 0)

    # Immutable "safe" configuration for switches and sweeper
    def reset_configure(self):
        self.check_ept('hf_output_status', 0)
        self.check_ept('hf_power', -50)
        self.check_ept('esr_tickler_switch', 1)
        for i in range(1, 6):
            self.check_ept('esr_coil_{}_switch_status'.format(i), 0)

    def single_measure(self, coilnum):
        self.check_ept('hf_output_status', 1)
        self.check_ept('esr_coil_{}_switch_status'.format(coilnum), 1)
        time = datetime.today().ctime()
        self.raw_get_ept('lockin_take_data')
        # HF sweep takes 60 sec
        while True:
            status = self.raw_get_ept('lockin_curve_status')
            logger.info(status)
            if status.split(',')[0] == '0':
                break
        self.check_ept('hf_output_status', 0)
        self.check_ept('esr_coil_{}_switch_status'.format(coilnum), 0)

        # Get the lockin data
        data = {}
        data['sweep_out'] = lockin_result_to_array(self.drip_cmd('lockin_instrument.grab_data', 'adc'))
        data['lockin_x_data'] = lockin_result_to_array(self.drip_cmd('lockin_instrument.grab_data', 'x'))
        data['lockin_y_data'] = lockin_result_to_array(self.drip_cmd('lockin_instrument.grab_data', 'y'))
        data['lockin_mag'] = lockin_result_to_array(self.drip_cmd('lockin_instrument.grab_data', 'mag'))
        ten_volts = 10.0
        frequency_span = self.hf_stop_freq - self.hf_start_freq
        data['frequency'] = self.hf_start_freq + frequency_span * data['sweep_out']/ten_volts
        data['amplitude'] = data['lockin_x_data'] + 1j*data['lockin_y_data']

        # Weiner filter and analysis
        filter_data = WeinerFilter(data['frequency'],data['amplitude'],'lorentzian')
            #TODO a fit would be more appropriate to get uncertainty
        max_freq_index = numpy.argmax(filter_data['result'])
        res_freq = filter_data['freqs'][max_freq_index]
        b_field=4.*numpy.pi*res_freq/(self.esr_g_factor*self.electron_cyclotron_frequency)
        self.data_dict[coilnum] = { 'field' : b_field,
                                    'res_freq' : res_freq,
                                    'time' : time,
                                    'raw_data' : { 'frequency' : data['frequency'],
                                                   'amplitude' : data['amplitude'],
                                                   'amp_x' : data['lockin_x_data'],
                                                   'amp_y' : data['lockin_y_data'],
                                                   'amp_t' : data['lockin_mag'] },
                                    'filtered_data' : filter_data }
        logger.info("Coil #{} result: field = {}, res_freq = {}".format(coilnum,b_field,res_freq))
        logger.info("G: {}, L: {}, L2: {}".format(numpy.argmax(filter_data['result3']),max_freq_index,numpy.argmax(filter_data['result2'])))

        return b_field

    def save_data(self):
        outfile = TFile("/home/pettus/test.root", "recreate")

        from ROOT import MyStruct1, MyStruct2
        struct1 = MyStruct1()
        struct2 = MyStruct2()

        tree = TTree("header", "metadata")
        tree.Branch("insert", struct1, "string_pot_mm/F:coil1_relay/I:coil1_polarity:coil1_output:coil1_current_A/F\
                                                       :coil2_relay/I:coil2_polarity:coil2_output:coil2_current_A/F\
                                                       :coil3_relay/I:coil3_polarity:coil3_output:coil3_current_A/F\
                                                       :coil4_relay/I:coil4_polarity:coil4_output:coil4_current_A/F\
                                                       :coil5_relay/I:coil5_polarity:coil5_output:coil5_current_A/F")
        tree.Branch("lockin", AddressOf(struct1, "fLNPts"), "lockin_n_pts/I:lockin_sample_interval_ms:lockin_trigger/I\
                                                            :lockin_curve_mask:lockin_srq_mask:lockin_ac_gain_dB/I\
                                                            :lockin_osc_amp_V/F:lockin_osc_freq_Hz:lockin_sensitivity_V:lockin_tc_s")
        tree.Branch("sweeper", AddressOf(struct1, "fSStart"), "sweeper_start_freq_Hz/F:sweeper_stop_freq_Hz:sweeper_power_dBm/F\
                                                              :sweeper_dwell_time_s:sweeper_n_pts/I")

        insert = self.raw_get_ept("run_metadata")
        struct1.fStringPot = insert['string_pot']
        struct1.fC1Relay = int(insert['trap_coil_1_relay_status'])
        struct1.fC1Polarity = int(insert['trap_coil_1_polarity'])
        struct1.fC1Output = int(insert['trap_coil_1_output_status'])
        struct1.fC1Current = insert['trap_coil_1_current_output']
        struct1.fC2Relay = int(insert['trap_coil_2_relay_status'])
        struct1.fC2Polarity = int(insert['trap_coil_2_polarity'])
        struct1.fC2Output = int(insert['trap_coil_2_output_status'])
        struct1.fC2Current = insert['trap_coil_2_current_output']
        struct1.fC3Relay = int(insert['trap_coil_3_relay_status'])
        struct1.fC3Polarity = int(insert['trap_coil_3_polarity'])
        struct1.fC3Output = int(insert['trap_coil_3_output_status'])
        struct1.fC3Current = insert['trap_coil_3_current_output']
        struct1.fC4Relay = int(insert['trap_coil_4_relay_status'])
        struct1.fC5Polarity = int(insert['trap_coil_4_polarity'])
        struct1.fC4Output = int(insert['trap_coil_4_output_status'])
        struct1.fC4Current = insert['trap_coil_4_current_output']
        struct1.fC5Relay = int(insert['trap_coil_5_relay_status'])
        struct1.fC5Polarity = int(insert['trap_coil_5_polarity'])
        struct1.fC5Output = int(insert['trap_coil_5_output_status'])
        struct1.fC5Current = insert['trap_coil_5_current_output']

        lockin = self.raw_get_ept("lockin_settings")
        struct1.fLNPts = int(lockin['lockin_n_points'])
        struct1.fLInterval = int(lockin['lockin_sampling_interval'])
        struct1.fLTrigger = int(lockin['lockin_trigger'])
        struct1.fLCurve = int(lockin['lockin_curve_mask'])
        struct1.fLSRQ = int(lockin['lockin_srq_mask'])
        struct1.fLACGain = lockin['lockin_ac_gain']
        struct1.fLOAmp = float(lockin['lockin_osc_amp'])
        struct1.fLOFreq = float(lockin['lockin_osc_freq'])
        struct1.fLSens = float(lockin['lockin_sensitivity'])
        struct1.fLTC = float(lockin['lockin_time_constant'])

        sweeper = self.raw_get_ept("sweeper_settings")
        key = "hf_freq_mode"
        logger.info("{} - {} - {}".format(key, type(sweeper[key]), sweeper[key]))
        struct1.fSStart = float(sweeper['hf_start_freq'])
        struct1.fSStop = float(sweeper['hf_stop_freq'])
        struct1.fSPower = float(sweeper['hf_power'])
        struct1.fSDwell = float(sweeper['hf_dwell_time'])
        struct1.fSNPts = int(sweeper['hf_n_sweep_points'])

        tree.Fill()
        outfile.Write()

        for coil in range(1, 6):
            if coil not in self.data_dict:
                logger.warning("ESR coil #{} data not available".format(coil))
                continue
            pts = len(self.data_dict[coil]['raw_data']['frequency'])
            if pts != self.lockin_n_points:
                logger.warning("ESR coil #{}: unexpected trace length {}".format(coil, pts))
            tree = TTree("coil{}".format(coil), "coil {} data".format(coil))
            tree.Branch("raw", struct2, "freq/F:amp_x:amp_y:amp_mag")
            tree.Branch("filt", AddressOf(struct2, "fF1"), "freq/F:result:target:result2:target2:result3:target3:mag:magx")
            
            for i in range(pts):
                struct2.fR1 = self.data_dict[coil]['raw_data']['frequency'][i]
                struct2.fR2 = self.data_dict[coil]['raw_data']['amp_x'][i]
                struct2.fR3 = self.data_dict[coil]['raw_data']['amp_y'][i]
                struct2.fR4 = self.data_dict[coil]['raw_data']['amp_t'][i]
                struct2.fF1 = self.data_dict[coil]['filtered_data']['freqs'][i]
                struct2.fF2 = self.data_dict[coil]['filtered_data']['result'][i]
                struct2.fF3 = self.data_dict[coil]['filtered_data']['target'][i]
                struct2.fF4 = self.data_dict[coil]['filtered_data']['result2'][i]
                struct2.fF5 = self.data_dict[coil]['filtered_data']['target2'][i]
                struct2.fF6 = self.data_dict[coil]['filtered_data']['result3'][i]
                struct2.fF7 = self.data_dict[coil]['filtered_data']['target3'][i]
                struct2.fF8 = self.data_dict[coil]['filtered_data']['mag'][i]
                struct2.fF9 = self.data_dict[coil]['filtered_data']['magx'][i]
                tree.Fill()
            outfile.Write()
        outfile.Close()

    def root_setup(self):
	gROOT.ProcessLine("struct MyStruct1 {\
                               Float_t fStringPot;\
                               Int_t fC1Relay;\
                               Int_t fC1Polarity;\
                               Int_t fC1Output;\
                               Float_t fC1Current;\
                               Int_t fC2Relay;\
                               Int_t fC2Polarity;\
                               Int_t fC2Output;\
                               Float_t fC2Current;\
                               Int_t fC3Relay;\
                               Int_t fC3Polarity;\
                               Int_t fC3Output;\
                               Float_t fC3Current;\
                               Int_t fC4Relay;\
                               Int_t fC4Polarity;\
                               Int_t fC4Output;\
                               Float_t fC4Current;\
                               Int_t fC5Relay;\
                               Int_t fC5Polarity;\
                               Int_t fC5Output;\
                               Float_t fC5Current;\
                               Int_t fLNPts;\
                               Int_t fLInterval;\
                               Int_t fLTrigger;\
                               Int_t fLCurve;\
                               Int_t fLSRQ;\
                               Int_t fLACGain;\
                               Float_t fLOAmp;\
                               Float_t fLOFreq;\
                               Float_t fLSens;\
                               Float_t fLTC;\
                               Float_t fSStart;\
                               Float_t fSStop;\
                               Float_t fSPower;\
                               Float_t fSDwell;\
                               Int_t fSNPts;\
                           };");
	gROOT.ProcessLine("struct MyStruct2 {\
                               Float_t fR1;\
                               Float_t fR2;\
                               Float_t fR3;\
                               Float_t fR4;\
                               Float_t fF1;\
                               Float_t fF2;\
                               Float_t fF3;\
                               Float_t fF4;\
                               Float_t fF5;\
                               Float_t fF6;\
                               Float_t fF7;\
                               Float_t fF8;\
                               Float_t fF9;\
	                   };");


    def debug_run(self):
        self.configure_instruments()
        self.single_measure(1)
        #logger.info(self.data_dict[1])
        self.reset_configure()
        self.save_data()

    def run_scan(self):
        self.configure_instruments()
        for i in range(1, 6):
            self.single_measure(i)
        self.save_data()
        logger.info(self.data_dict)
        self.reset_configure()
        return [self.data_dict[i]['field'] for i in range(1,6)]


    def drip_cmd(self, cmdname, val):
        request_message = core.RequestMessage(msgop=core.OP_CMD,
                                              payload={'values':[val]})
        a_result=self.portal.send_request(request=request_message,target=cmdname)
        if a_result.retcode == 0 :
            return a_result.payload['values'][0]
        else:
            return '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)

    def raw_get_ept(self, endptname):
        request_message = core.RequestMessage(msgop=core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)
        if a_result.retcode == 0 :
            return a_result.payload['value_raw']
        else:
            return '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)

    def set_ept(self, endptname, val):
        request_message = core.RequestMessage(msgop=core.OP_SET,
                                              payload={'values':[val]})
        a_result=self.portal.send_request(request=request_message,target=endptname)
        if a_result.retcode != 0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
            logger.alert("got error "+ret_rep)
        else:
            if 'values' in a_result.payload:
                ret_val = a_result.payload['values'][0]
            elif 'value_raw' in a_result.payload:
                ret_val = a_result.payload['value_raw']
            else:
                logger.info("return payload is {}".format(a_result.payload))
                ret_val = a_result.payload
        return ret_val

    def check_ept(self, endptname, val):
        ret_val = self.set_ept(endptname, val)
        if isinstance(val, int) or isinstance(val, float):
            ret_val = float(ret_val)
        elif not isinstance(val, str):
            logger.alert("ret_val is of type {} with value {}".format(type(ret_val), ret_val))
            raise TypeError
        if ret_val != val:
            raise core.exceptions.DriplineValueError("Failure to set endpoint: {}".format(endptname))
        return


def WeinerFilter(freq_data, amp_data, target='gaussian'):
    logger.warning('doing filter on target: {}'.format(target))
    data = zip(freq_data, amp_data)
    data.sort()
    f,v= zip(*data)
    frequencies = numpy.array(f, dtype=float)
    voltages = numpy.array(v, dtype=complex)
    width = (frequencies[numpy.argmin(voltages)] - frequencies[numpy.argmax(voltages)]) / 2.
    x1 = (frequencies - frequencies[0])
    x2 = (frequencies - frequencies[-1])
    gderiv1 = -x1 * numpy.exp(-x1**2 / 2. / width**2) * numpy.exp(0.5) / width
    gderiv2 = -x2 * numpy.exp(-x2**2 / 2. / width**2) * numpy.exp(0.5) / width
    lderiv1 = -x1 / (x1**2 + (width * 3.**0.5)**2)**2 * 16. * width**3
    lderiv2 = -x2 / (x2**2 + (width * 3.**0.5)**2)**2 * 16. * width**3
    ld1 = -x1 / (x1**2 + width**2) * 2. * width
    ld2 = -x2 / (x2**2 + width**2) * 2. * width
    targets = {}
    targets['gaussian'] = numpy.concatenate((gderiv1[:len(gderiv1)/2], gderiv2[len(gderiv2)/2:]))
    targets['lorentzian'] = numpy.concatenate((lderiv1[:len(lderiv1)/2], lderiv2[len(lderiv2)/2:]))
    targets['lorentzish'] = numpy.concatenate((ld1[:len(ld1)/2], ld2[len(ld2)/2:]))
    target_signal = targets[target]
    if not sum(target_signal != 0):
        raise ValueError("target signal identically 0, did you give width in Hz?")
    data_fft = numpy.fft.fft(voltages)
    data_fft[0] = 0
    filtered = {}
    for shape in targets:
        target_fft = numpy.fft.fft(targets[shape])
        filtered[shape] = numpy.fft.ifft(data_fft * target_fft)
    return {'freqs': frequencies,
            'mag': numpy.abs(voltages),
            'magx': numpy.real(voltages),
            'result': numpy.abs(filtered['gaussian']),
            'target': targets['gaussian'],
            'result2': numpy.abs(filtered['lorentzian']),
            'target2': targets['lorentzian'],
            'result3': numpy.abs(filtered['lorentzish']),
            'target3': targets['lorentzish']
           }
