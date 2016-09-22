from __future__ import absolute_import
__all__ = []

import os
import numpy
import logging
from datetime import datetime
from time import sleep
try:
    from ROOT import AddressOf, gROOT, gStyle, TCanvas, TF1, TFile, TGraph,\
                     TGraphErrors, TMultiGraph, TTimeStamp, TTree
except ImportError:
    pass

from dripline import core

logger = logging.getLogger(__name__)


__all__.append('ESR_Measurement')
#@fancy_doc
class ESR_Measurement(core.Endpoint):
    """
    Operate the ESR system to measure the B-field off-axis.
    Methods are sorted by order of call within run_scan.
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
                 hf_sweep_order,
                 hf_start_freq,
                 hf_stop_freq,
                 hf_power,
                 hf_n_sweep_points,
                 hf_dwell_time,
                 **kwargs):
        # note that if the imports are changed to not include gROOT, change this to test something that is imported
        if not 'gROOT' in globals():
            raise ImportError('PyROOT not found, required for ESR_Measurement class')
        core.Endpoint.__init__(self,**kwargs)
        # Settings for lockin and sweeper
        self.lockin_n_points = self._default_lockin_n_points = lockin_n_points
        self.lockin_sampling_interval = self._default_lockin_sampling_interval = lockin_sampling_interval
        self.lockin_trigger = self._default_lockin_trigger = lockin_trigger
        self.lockin_curve_mask = self._default_lockin_curve_mask = lockin_curve_mask
        self.lockin_srq_mask = self._default_lockin_srq_mask = lockin_srq_mask
        self.lockin_osc_amp = self._default_lockin_osc_amp = lockin_osc_amp
        self.lockin_osc_freq = self._default_lockin_osc_freq = lockin_osc_freq
        self.lockin_ac_gain = self._default_lockin_ac_gain = lockin_ac_gain
        self.lockin_sensitivity = self._default_lockin_sensitivity = lockin_sensitivity
        self.lockin_time_constant = self._default_lockin_time_constant = lockin_time_constant
        self.hf_sweep_order = self._default_hf_sweep_order = hf_sweep_order
        self.hf_start_freq = self._default_hf_start_freq = float(hf_start_freq)
        self.hf_stop_freq = self._default_hf_stop_freq = float(hf_stop_freq)
        self.hf_power = self._default_hf_power = hf_power
        self.hf_n_sweep_points = self._default_hf_n_sweep_points = hf_n_sweep_points
        self.hf_dwell_time = self._default_hf_dwell_time = hf_dwell_time
        # Constants and analysis parameters
        self.shape = 'gaussian' # functional form of fit/filter
        self.freq_span = 0 # calculated from sweeper frequency range in capture_settings
        self._electron_cyclotron_frequency = 1.758820024e11 # rad s^-1 T^-1
        self._esr_g_factor = 2.0026 # g-factor for BDPA (from literature)
        self._freq_rescale = 1e-6 # frequency looks better in MHz
        self._bfield_factor = 4.*numpy.pi / (self._esr_g_factor*self._electron_cyclotron_frequency*self._freq_rescale) # frequency to field conversion factor
        self._sweep_voltage = 10.0 # voltage range for "SWEEP OUT" from ardbeg
        # Output storage
        self.data_dict = {} # reset in run_scan 
        self.root_dict = {} # reset in run_scan
        self.settings = {} # reset in capture_settings
        self.root_setup()


    def run_scan(self, config_instruments=True, restore_defaults=True, coils=[1,2,3,4,5], n_fits=2, **kwargs):
        '''
        Wraps all ESR functionality into single method call with tunable arguments.
        This function should interface with run_scripting through the action_esr_run method.
        '''
        logger.info(kwargs)
        self.data_dict = {}
        self.root_dict = {}
        if config_instruments:
            self.configure_instruments(restore_defaults)
        self.capture_settings()
        for i in coils:
            self.single_measure(i)
            self.single_analysis(i, n_fits)
            # FIXME: analysis can be spawned and run in background
        if config_instruments:
            self.reset_configure()
            # FIXME: warning to user to reset_configure manually if not performed here
        self.save_data(n_fits)
        #logger.info(self.data_dict)
        return { coil : self.data_dict[coil]['result']['fit'] for coil in self.data_dict }


    def configure_instruments(self, reset):
        '''
        Configure instruments to default settings.
        '''
        if reset:
            self.restore_presets()
        # lockin controls
        self.check_ept('lockin_n_points', self.lockin_n_points)
        self.check_ept('lockin_sampling_interval', self.lockin_sampling_interval)
        self.check_ept('lockin_trigger', self.lockin_trigger)
        self.check_ept('lockin_curve_mask', self.lockin_curve_mask)
        self.check_ept('lockin_srq_mask', self.lockin_srq_mask)
        self.check_ept('lockin_osc_amp', self.lockin_osc_amp)
        self.check_ept('lockin_osc_freq', self.lockin_osc_freq)
        #self.check_ept('lockin_ac_gain', self.lockin_ac_gain) # Lockin settings currently bind ACGAIN to SEN parameter
        self.check_ept('lockin_sensitivity', self.lockin_sensitivity)
        self.check_ept('lockin_time_constant', self.lockin_time_constant)
        # sweeper controls
        while True:
            err_msg = self.raw_get_ept('hf_error_check')
            if err_msg == '+0,"No error"':
                break
            logger.warning("Clearing sweeper error queue: {}".format(err_msg))
        self.check_ept('hf_output_status', 0)
        self.check_ept('hf_freq_mode', 'LIST')
        self.check_ept('hf_sweep_order', str(self.hf_sweep_order))
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
        for coil in range(1, 6):
            self.check_ept('esr_coil_{}_switch_status'.format(coil), 0)

    def restore_presets(self):
        '''
        Reset all internal variables to presets loaded from config
        '''
        # lockin presets
        self.lockin_n_points = self._default_lockin_n_points
        self.lockin_sampling_interval = self._default_lockin_sampling_interval
        self.lockin_trigger = self._default_lockin_trigger
        self.lockin_curve_mask = self._default_lockin_curve_mask
        self.lockin_srq_mask = self._default_lockin_srq_mask
        self.lockin_osc_amp = self._default_lockin_osc_amp
        self.lockin_osc_freq = self._default_lockin_osc_freq
        self.lockin_ac_gain = self._default_lockin_ac_gain
        self.lockin_sensitivity = self._default_lockin_sensitivity
        self.lockin_time_constant = self._default_lockin_time_constant
        # sweeper presets
        self.hf_sweep_order = self._default_hf_sweep_order
        self.hf_start_freq = self._default_hf_start_freq
        self.hf_stop_freq = self._default_hf_stop_freq
        self.hf_power = self._default_hf_power
        self.hf_n_sweep_points = self._default_hf_n_sweep_points
        self.hf_dwell_time = self._default_hf_dwell_time

    def reset_configure(self):
        '''
        Immutable "safe" configuration for switches and sweeper
        '''
        self.check_ept('hf_output_status', 0)
        self.check_ept('hf_power', -50)
        self.check_ept('esr_tickler_switch', 1)
        for coil in range(1, 6):
            self.check_ept('esr_coil_{}_switch_status'.format(coil), 0)

    def capture_settings(self):
        '''
        Record current status of the insert, lockin, and sweeper
        FIXME: Endpoints should either be locked here or already
        '''
        self.settings = {}
        self.settings['insert'] = self.raw_get_ept("run_metadata")
        self.settings['lockin'] = self.raw_get_ept("lockin_settings")
        self.settings['sweeper'] = self.raw_get_ept("sweeper_settings")
        self.settings['sweeper']['hf_start_freq'] = float(self.settings['sweeper']['hf_start_freq'])
        if self.settings['sweeper']['hf_start_freq'] != self.hf_start_freq:
            logger.warning("Mismatch of sweeper start frequency.  Using {} but internal value is {}".\
                            format(self.settings['sweeper']['hf_start_freq'], self.hf_start_freq))
        self.settings['sweeper']['hf_stop_freq'] = float(self.settings['sweeper']['hf_stop_freq'])
        if self.settings['sweeper']['hf_stop_freq'] != self.hf_stop_freq:
            logger.warning("Mismatch of sweeper stop frequency.  Using {} but internal value is {}".\
                            format(self.settings['sweeper']['hf_stop_freq'], self.hf_stop_freq))
        # FIXME: pass warnings out to run_scripting or some ESR error queue
        self.freq_span = self.settings['sweeper']['hf_stop_freq'] - self.settings['sweeper']['hf_start_freq']

    def single_measure(self, coil):
        '''
        Communicate with lockin, sweeper, and switches to execute single ESR coil scan.
        Data is retrieved but not analyzed.
        '''
        self.check_ept('hf_output_status', 1)
        self.check_ept('esr_coil_{}_switch_status'.format(coil), 1)
        time = datetime.today().ctime()
        timestamp = TTimeStamp()
        self.raw_get_ept('lockin_take_data')
        # HF sweep takes 60 sec
        while True:
            status = self.raw_get_ept('lockin_curve_status')
            logger.info(status)
            if status.split(',')[0] == '0':
                break
            else:
                time_est = min( 5, (self.lockin_n_points-int(status.split(',')[3]))*self.lockin_sampling_interval*1e-3 )
                logger.info("sleeping for {} sec".format(time_est))
                sleep(time_est)
        self.check_ept('hf_output_status', 0)
        self.check_ept('esr_coil_{}_switch_status'.format(coil), 0)

        # Get the lockin data
        raw = { 'adc' : self.pull_lockin_data('adc'),
                'x' : self.pull_lockin_data('x'),
                'y' : self.pull_lockin_data('y') }
        self.data_dict.update( { coil : { 'raw_data' : raw,
                                          'time' : time } } )
        self.root_dict.update( { coil : { 'time' : timestamp } } )

    def single_analysis(self, coil, n_fits):
        '''
        Perform analysis on single raw data trace:
        - Convert sweeper out voltage to frequency
        - Calculate crossing frequency via Wiener optimal filter
        - Fit trace with ROOT Minuit
        '''
        data = numpy.column_stack((self.data_dict[coil]['raw_data']['adc'],
                                   self.data_dict[coil]['raw_data']['x']*1e6,
                                   self.data_dict[coil]['raw_data']['y']*1e6))
        data = data.ravel().view([('f','float'), ('x','float'), ('y','float')])
        data['f'] = (self.settings['sweeper']['hf_start_freq'] + self.freq_span*data['f']/self._sweep_voltage) * self._freq_rescale
        fspan = data['f'][-1] - data['f'][0] + self.freq_span*self._freq_rescale
        numpy.ndarray.sort(data)

        # Resonant frequency analysis - Wiener filter and ROOT fit
        filtered = wiener_filter(data, shape=self.shape)
        fitted = root_fit(data, fits=n_fits, span=fspan, shape=self.shape)
        self.data_dict[coil].update( { 'result' : { 'filt' : filtered['result']*self._bfield_factor,
                                                    'filt_e' : filtered['error']*self._bfield_factor,
                                                    'fit' : fitted.pop('result')*self._bfield_factor,
                                                    'fit_e' : fitted.pop('error')*self._bfield_factor } } )
        self.root_dict[coil].update( { 'fits' : fitted } )
        # FIXME: Pass warnings back if self.data_dict[coil]['result']['fit'/'filt'] == 0

        return (self.data_dict[coil]['result']['fit'], self.data_dict[coil]['result']['fit_e'])

    def save_data(self, n_fits):
        '''
        Save data to output file (currently only ROOT)
        '''
        outpath = os.environ["HOME"] + "/GoogleDrive/Project8/Data/ESRData/Phase2/{:%Y%m%d_%H%M%S}/".format(datetime.now())
        if not os.path.exists(outpath):
            logger.info("Creating directory {}".format(outpath))
            os.makedirs(outpath)
        outfile = TFile(outpath+"esr.root", "recreate")

        from ROOT import MyStruct1, MyStruct2, MyStruct3, MyStruct4
        struct1 = MyStruct1()
        struct2 = MyStruct2()
        struct3 = MyStruct3()
        struct4 = MyStruct4()

        htree = TTree("header", "metadata")
        htree.Branch("insert", struct1, "string_pot_mm/F:coil1_relay/I:coil1_polarity:coil1_output:coil1_current_A/F\
                                                        :coil2_relay/I:coil2_polarity:coil2_output:coil2_current_A/F\
                                                        :coil3_relay/I:coil3_polarity:coil3_output:coil3_current_A/F\
                                                        :coil4_relay/I:coil4_polarity:coil4_output:coil4_current_A/F\
                                                        :coil5_relay/I:coil5_polarity:coil5_output:coil5_current_A/F")
        htree.Branch("lockin", AddressOf(struct1, "fLNPts"), "lockin_n_pts/I:lockin_sample_interval_ms:lockin_trigger/I\
                                                             :lockin_curve_mask:lockin_srq_mask:lockin_ac_gain_dB/I\
                                                             :lockin_osc_amp_V/F:lockin_osc_freq_Hz:lockin_sensitivity_V:lockin_tc_s")
        htree.Branch("sweeper", AddressOf(struct1, "fSStart"), "sweeper_start_freq_Hz/F:sweeper_stop_freq_Hz:sweeper_power_dBm/F\
                                                               :sweeper_dwell_time_s:sweeper_n_pts/I:sweeper_mode[8]/C:sweeper_order[8]")

        struct1.fStringPot = self.settings['insert']['string_pot']
        struct1.fC1Relay = int(self.settings['insert']['trap_coil_1_relay_status'])
        struct1.fC1Polarity = int(self.settings['insert']['trap_coil_1_polarity'])
        struct1.fC1Output = int(self.settings['insert']['trap_coil_1_output_status'])
        struct1.fC1Current = self.settings['insert']['trap_coil_1_current_output']
        struct1.fC2Relay = int(self.settings['insert']['trap_coil_2_relay_status'])
        struct1.fC2Polarity = int(self.settings['insert']['trap_coil_2_polarity'])
        struct1.fC2Output = int(self.settings['insert']['trap_coil_2_output_status'])
        struct1.fC2Current = self.settings['insert']['trap_coil_2_current_output']
        struct1.fC3Relay = int(self.settings['insert']['trap_coil_3_relay_status'])
        struct1.fC3Polarity = int(self.settings['insert']['trap_coil_3_polarity'])
        struct1.fC3Output = int(self.settings['insert']['trap_coil_3_output_status'])
        struct1.fC3Current = self.settings['insert']['trap_coil_3_current_output']
        struct1.fC4Relay = int(self.settings['insert']['trap_coil_4_relay_status'])
        struct1.fC4Polarity = int(self.settings['insert']['trap_coil_4_polarity'])
        struct1.fC4Output = int(self.settings['insert']['trap_coil_4_output_status'])
        struct1.fC4Current = self.settings['insert']['trap_coil_4_current_output']
        struct1.fC5Relay = int(self.settings['insert']['trap_coil_5_relay_status'])
        struct1.fC5Polarity = int(self.settings['insert']['trap_coil_5_polarity'])
        struct1.fC5Output = int(self.settings['insert']['trap_coil_5_output_status'])
        struct1.fC5Current = self.settings['insert']['trap_coil_5_current_output']

        struct1.fLNPts = int(self.settings['lockin']['lockin_n_points'])
        struct1.fLInterval = int(self.settings['lockin']['lockin_sampling_interval'])
        struct1.fLTrigger = int(self.settings['lockin']['lockin_trigger'])
        struct1.fLCurve = int(self.settings['lockin']['lockin_curve_mask'])
        struct1.fLSRQ = int(self.settings['lockin']['lockin_srq_mask'])
        struct1.fLACGain = self.settings['lockin']['lockin_ac_gain']
        struct1.fLOAmp = float(self.settings['lockin']['lockin_osc_amp'])
        struct1.fLOFreq = float(self.settings['lockin']['lockin_osc_freq'])
        struct1.fLSens = float(self.settings['lockin']['lockin_sensitivity'])
        struct1.fLTC = float(self.settings['lockin']['lockin_time_constant'])

        struct1.fSStart = self.settings['sweeper']['hf_start_freq']
        struct1.fSStop = self.settings['sweeper']['hf_stop_freq']
        struct1.fSPower = float(self.settings['sweeper']['hf_power'])
        struct1.fSDwell = float(self.settings['sweeper']['hf_dwell_time'])
        struct1.fSNPts = int(self.settings['sweeper']['hf_n_sweep_points'])
        struct1.fSMode = self.settings['sweeper']['hf_freq_mode']
        struct1.fSOrder  = self.settings['sweeper']['hf_sweep_order']

        htree.Fill()
        htree.Write()

        atree = TTree("analysis", "global parameters")
        atree.Branch("constants", struct4, "shape[12]/C:field_factor/D:n_fits/I")
        struct4.fShape = self.shape
        struct4.fFactor = self._bfield_factor
        struct4.fNFit = n_fits
        atree.Fill()
        atree.Write()

        rtree = TTree("result", "ESR scan results")
        ttree = TTree("timestamp", "ESR measure start TTimeStamp")
        for coil in range(1, 6):
            if coil not in self.data_dict:
                logger.warning("ESR coil #{} data not available".format(coil))
                continue
            pts = len(self.data_dict[coil]['raw_data']['adc'])
            if pts != self.lockin_n_points:
                logger.warning("ESR coil #{}: unexpected trace length {}".format(coil, pts))
            dtree = TTree("coil{}".format(coil), "coil {} data".format(coil))
            dtree.Branch("raw", struct2, "adc/D:x:y")

            for i in range(pts):
                struct2.fRaw1 = self.data_dict[coil]['raw_data']['adc'][i]
                struct2.fRaw2 = self.data_dict[coil]['raw_data']['x'][i]
                struct2.fRaw3 = self.data_dict[coil]['raw_data']['y'][i]
                dtree.Fill()
            dtree.Write()

            rbranch = rtree.Branch("coil{}".format(coil), struct3, "filt_field_Hz/D:filt_field_e_T/D\
                                                                      :fit_field_T:fit_field_e_T")
            struct3.fFiltB = self.data_dict[coil]['result']['filt']
            struct3.fFiltBE = self.data_dict[coil]['result']['filt_e']
            struct3.fFitB = self.data_dict[coil]['result']['fit']
            struct3.fFitBE = self.data_dict[coil]['result']['fit_e']
            rbranch.Fill()

            tbranch = ttree.Branch("coil{}".format(coil), self.root_dict[coil]['time'])
            tbranch.Fill()

        rtree.Fill()
        rtree.Write()
        ttree.Fill()
        ttree.Write()

        outfile.mkdir("Plots")
        outfile.cd("Plots")
        esr_trace_plots({coil:self.root_dict[coil]['fits'] for coil in self.root_dict}, outfile, outpath)
        field_plot({coil:self.data_dict[coil]['result'] for coil in self.data_dict}, outfile, outpath)
        outfile.Close()


    def root_setup(self):

        gROOT.Reset()
        gROOT.SetBatch()
        gStyle.SetOptStat     (0)
        gStyle.SetOptFit      (0)
        gStyle.SetTitleSize   (0.045,"xy")
        gStyle.SetTitleOffset (0.8,  "xy")
        gStyle.SetPadTickY    (1)
        gStyle.SetPadTickX    (1)

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
                               Char_t fSMode[8];\
                               Char_t fSOrder[8];\
                           };");
        gROOT.ProcessLine("struct MyStruct2 {\
                               Double_t fRaw1;\
                               Double_t fRaw2;\
                               Double_t fRaw3;\
	                   };");
        gROOT.ProcessLine("struct MyStruct3 {\
                               Double_t fFiltB;\
                               Double_t fFiltBE;\
                               Double_t fFitB;\
                               Double_t fFitBE;\
                           };");
        gROOT.ProcessLine("struct MyStruct4 {\
                               Char_t fShape[12];\
                               Double_t fFactor;\
                               Int_t fNFit;\
                           };");

    def pull_lockin_data(self, key):
        raw = self.drip_cmd('lockin_interface.grab_data', key)
        return numpy.array(raw.replace('\x00','').split(';'), dtype=float)

    def drip_cmd(self, cmdname, val):
        request_message = core.RequestMessage(msgop=core.OP_CMD,
                                              payload={'values':[val]})
        a_result=self.portal.send_request(request=request_message, target=cmdname, timeout=20)
        if a_result.retcode == 0 :
            return a_result.payload['values'][0]
        else:
            return '{} -> returned error <{}>:{}'.format(cmdname, a_result.retcode, a_result.return_msg)

    def raw_get_ept(self, endptname):
        request_message = core.RequestMessage(msgop=core.OP_GET)
        a_result=self.portal.send_request(request=request_message, target=endptname, timeout=20)
        if a_result.retcode == 0 :
            return a_result.payload['value_raw']
        else:
            return '{} -> returned error <{}>:{}'.format(endptname, a_result.retcode, a_result.return_msg)

    def set_ept(self, endptname, val):
        request_message = core.RequestMessage(msgop=core.OP_SET,
                                              payload={'values':[val]})
        a_result=self.portal.send_request(request=request_message,target=endptname)
        if a_result.retcode != 0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endptname, a_result.retcode, a_result.return_msg)
            logger.warning("got error "+ret_rep)
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
            logger.warning("ret_val is of type {} with value {}".format(type(ret_val), ret_val))
            raise TypeError
        if ret_val != val:
            raise core.exceptions.DriplineValueError("Failure to set endpoint: {}".format(endptname))
        return


def wiener_filter(data, shape='gaussian'):
    '''
    Apply Wiener filter to data to crossing frequency
    '''
    freq = data['f']
    volt = data['x'] + 1j*data['y']
    logger.info('doing filter on target: {}'.format(shape))
    width = (freq[numpy.argmin(volt)] - freq[numpy.argmax(volt)]) / 2.
    x1 = (freq - freq[0])
    x2 = (freq - freq[-1])
    if shape == 'gaussian':
        deriv1 = -x1 * numpy.exp(-x1**2 / 2. / width**2) * numpy.exp(0.5) / width
        deriv2 = -x2 * numpy.exp(-x2**2 / 2. / width**2) * numpy.exp(0.5) / width
    elif shape == 'lorentzian':
        deriv1 = -x1 / (x1**2 + (width * 3.**0.5)**2)**2 * 16. * width**3
        deriv2 = -x2 / (x2**2 + (width * 3.**0.5)**2)**2 * 16. * width**3
    target_signal = numpy.concatenate((deriv1[:len(deriv1)/2], deriv2[len(deriv2)/2:]))
    if not sum(target_signal != 0):
        raise ValueError("target signal identically 0, did you give width in Hz?")
    data_fft = numpy.fft.fft(volt)
    data_fft[0] = 0
    target_fft = numpy.fft.fft(target_signal)
    filtered = numpy.abs( numpy.fft.ifft(data_fft * target_fft) )

    # Lightly-tuned data-quality checks:
    fom1 = ( numpy.max(filtered) - numpy.mean(filtered) ) / numpy.std(filtered)
    #fom2 = abs(fit_field - b_field) / (fit_field_e**2 + b_field_e**2)**0.5
    if fom1 < 2.5:
        res_freq = 0
        res_freq_e = 0
        logger.warning("Rejecting Wiener filter result with figure-of-merit = {}".format(fom1))
    else:
        index = numpy.argmax( numpy.abs(filtered) )
        res_freq = freq[index]
        res_freq_e = max(freq[index]-freq[index-1],
                         freq[index+1]-freq[index])

    return { 'result': res_freq,
             'error': res_freq_e }

def root_fit(data, fits, span, shape='gaussian'):
        '''
        Use ROOT fitting with Minuit to determine crossing frequency
        '''
        if shape != 'gaussian':
            raise NameError("unexpected fit form")
            # FIXME: expand to include Lorentzian

        # Calculate quick seed values
        p1 = numpy.argmax(data['x'])
        p2 = numpy.argmin(data['x'])
        s = (data['f'][p2] - data['f'][p1]) / 2.
        b = (data['f'][p2] + data['f'][p1]) / 2.
        a = (data['x'][p1] - data['x'][p2]) / (2. * s * numpy.exp(-0.5))
        gfit = TF1("gfit","(-(x-[1])*gaus(0)-[3])*(x>0)\
                              +(-[4]*(x+[1])*exp(-(x+[1])**2/2./[2]**2)-[5])*(x<0)")
        gfit.SetParameters(a,b,s,0,a/2,0)
        gfit.SetLineColor(4)

        f2 = numpy.concatenate((-data['f'][::-1], data['f']))
        xy = numpy.concatenate((data['y'][::-1], data['x']))
        fe = numpy.array(len(data['f']) * [span / (len(data['f']) - 1) / 6.], dtype=float)
        f2e = numpy.concatenate((fe, fe))
        if b < (data['f'][0] + data['f'][-1]) / 2.:
            xe = numpy.array(len(data['x']) * [numpy.std(data['x'][-50:])])
            ye = numpy.array(len(data['y']) * [numpy.std(data['y'][-50:])])
        else:
            xe = numpy.array(len(data['x']) * [numpy.std(data['x'][:50])])
            ye = numpy.array(len(data['y']) * [numpy.std(data['y'][:50])])
        xye = numpy.concatenate((ye, xe))

        scale = 1
        for ct in range(fits):
            xe = xe * scale
            ye = ye * scale
            xye = xye * scale
            plot1 = TGraphErrors(len(f2), f2, xy, f2e, xye)
            plot1.Fit("gfit","ME")
            scale = (gfit.GetChisquare() / gfit.GetNDF())**0.5
            logger.info("Chi-Square : {} / {}; rescale error by {}".format(gfit.GetChisquare(), gfit.GetNDF(), scale))
            if scale > 0.95 and scale < 1.05:
                logger.info("Acceptable error reached after fit #{}, aborting iterative scale and fit".format(ct+1))
                break

        plot1.SetName("xy_f")
        plot2 = TGraphErrors(len(data['f']), data['f']*1., data['y']*1., fe, ye)
        plot2.SetName("y_f")
        plot2.SetLineColor(2)
        gfit2 = TF1("gfit","-(x-[1])*gaus(0)-[3]", data['f'][0], data['f'][-1])
        gfit2.SetParameters(-gfit.GetParameter(4), gfit.GetParameter(1), gfit.GetParameter(2), gfit.GetParameter(5))
        gfit2.SetLineColor(3)

        ymax = max(numpy.max(data['x']), numpy.max(data['y']))
        ymin = min(numpy.min(data['x']), numpy.min(data['y']))
        yrng = ymax - ymin
        ymax += yrng/8.
        ymin -= yrng/8.
        plot2.GetYaxis().SetRangeUser(ymin, ymax)

        res_freq = gfit.GetParameter(1)
        res_freq_e = gfit.GetParError(1)
        if res_freq < data['f'][0] or res_freq > data['f'][-1]:
            logger.warning("Rejecting fit result with out-of-range resonant frequency = {} MHz".format(res_freq))
            res_freq = 0
            res_freq_e = 0
        # FIXME: better check of fit failure?

        return { 'graph_xy' : plot1,
                 'graph_y' : plot2,
                 'fit' : gfit,
                 'fit_y': gfit2,
                 'result' : res_freq,
                 'error' : res_freq_e }

def esr_trace_plots(fits, outfile, outpath):
        for coil in fits:
            can = TCanvas("can{}".format(coil), "coil{}".format(coil))
            fits[coil]['graph_y'].SetTitle("Coil {};Frequency (MHz);Amplitude (arb)".format(coil))
            fits[coil]['graph_y'].Draw("AL")
            fits[coil]['fit_y'].Draw("same")
            fits[coil]['graph_xy'].Draw("L")
            can.Write()
            can.SaveAs(outpath+"coil{}.pdf".format(coil))

def field_plot(results, outfile, outpath):
        filt = { coil : results[coil] for coil in results if (results[coil]['filt']!=0) }
        fit = { coil : results[coil] for coil in results if (results[coil]['fit']!=0) }
        if len(filt)==0 and len(fit)==0:
            logger.warning("No valid ESR measurements, skipping field_plot")
            return

        x1 = numpy.array([coil for coil in filt], dtype=float)
        x1e = numpy.zeros(len(x1), dtype=float)
        x2 = numpy.array([coil for coil in fit], dtype=float)
        x2e = numpy.zeros(len(x2), dtype=float)
        y1 = numpy.array([filt[coil]['filt'] for coil in filt], dtype=float)
        y1e = numpy.array([filt[coil]['filt_e'] for coil in filt], dtype=float)
        y2 = numpy.array([fit[coil]['fit'] for coil in fit], dtype=float)
        y2e = numpy.array([fit[coil]['fit_e'] for coil in fit], dtype=float)

        can = TCanvas("can0", "field")
        mg = TMultiGraph()
        if len(x1) != 0:
            g_filt = TGraphErrors(len(x1), x1, y1, x1e, y1e)
            mg.Add(g_filt)
        if len(x2) != 0:
            g_fit = TGraphErrors(len(x2), x2, y2, x2e, y2e)
            g_fit.SetLineColor(2)
            mg.Add(g_fit)
        mg.SetTitle("Field Map;ESR Coil Position;Field (T)")
        mg.Draw("AL")
        can.Write()
        can.SaveAs(outpath+"fieldmap.pdf")
