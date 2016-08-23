from __future__ import absolute_import
__all__ = []

import os
import numpy
import logging
from datetime import datetime
from time import sleep
from ROOT import AddressOf, gROOT, gStyle, TCanvas, TF1, TFile, TGraph, TGraphErrors, TMultiGraph, TTree

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
                 hf_sweep_order,
                 hf_start_freq,
                 hf_stop_freq,
                 hf_power,
                 hf_n_sweep_points,
                 hf_dwell_time,
                 **kwargs):
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
        self.shape = 'gaussian'
        self.electron_cyclotron_frequency = 1.758820024e11 # rad s^-1 T^-1
        self.esr_g_factor = 2.0026
        # Output storage
        self.data_dict = {}
        self.root_setup()

    # Configure instruments to default settings
    def configure_instruments(self, reset):
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

    # Reset all internal variables to presets loaded from config
    def restore_presets(self):
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

    # Immutable "safe" configuration for switches and sweeper
    def reset_configure(self):
        self.check_ept('hf_output_status', 0)
        self.check_ept('hf_power', -50)
        self.check_ept('esr_tickler_switch', 1)
        for coil in range(1, 6):
            self.check_ept('esr_coil_{}_switch_status'.format(coil), 0)

    def single_measure(self, coil, n_fits):
        self.check_ept('hf_output_status', 1)
        self.check_ept('esr_coil_{}_switch_status'.format(coil), 1)
        time = datetime.today().ctime()
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
        data = {}
        data['sweep_out'] = lockin_result_to_array(self.drip_cmd('lockin_interface.grab_data', 'adc'))
        data['lockin_x_data'] = lockin_result_to_array(self.drip_cmd('lockin_interface.grab_data', 'x'))
        data['lockin_y_data'] = lockin_result_to_array(self.drip_cmd('lockin_interface.grab_data', 'y'))
        ten_volts = 10.0
        frequency_span = self.hf_stop_freq - self.hf_start_freq
        data['frequency'] = self.hf_start_freq + frequency_span * data['sweep_out']/ten_volts
        data['amplitude'] = data['lockin_x_data'] + 1j*data['lockin_y_data']

        # Weiner filter and analysis
        filter_data = WeinerFilter(data['frequency'], data['amplitude'], self.shape)
            #TODO a fit would be more appropriate to get uncertainty
        max_freq_index = numpy.argmax(filter_data['result'])
        res_freq = filter_data['freqs'][max_freq_index]
        res_freq_e = max(filter_data['freqs'][max_freq_index] - filter_data['freqs'][max_freq_index-1],
                         filter_data['freqs'][max_freq_index+1] - filter_data['freqs'][max_freq_index])
        b_field = 4.*numpy.pi*res_freq / (self.esr_g_factor*self.electron_cyclotron_frequency)
        b_field_e = b_field * res_freq_e / res_freq
        fits = self.root_fits(data, n_fits)
        fit_freq = fits['fit'].GetParameter(1)
        fit_freq_e = fits['fit'].GetParError(1)
        fit_field = 4.e6*numpy.pi*fit_freq / (self.esr_g_factor*self.electron_cyclotron_frequency)
        fit_field_e = fit_field * fit_freq_e / fit_freq
        self.data_dict[coil] = { 'raw_data' : { 'frequency' : data['frequency'],
                                                'amp_x' : data['lockin_x_data'],
                                                'amp_y' : data['lockin_y_data'] },
                                 'filtered_data' : filter_data,
                                 'fits' : fits }
        fom1 = ( numpy.max(filter_data['result']) - numpy.mean(filter_data['result']) ) / numpy.std(filter_data['result'])
        #fom2 = abs(fit_field - b_field) / (fit_field_e**2 + b_field_e**2)**0.5
        if fom1 > 2.5 :
            self.data_dict[coil]['result'] = { 'filt_field' : b_field,
                                               'filt_field_e' : b_field_e,
                                               'fit_field' : fit_field,
                                               'fit_field_e' : fit_field_e,
                                               'res_freq' : res_freq,
                                               'time' : time }
        else:
            logger.warning("Rejecting ESR measurement for coil {}\nFigure of merit is {}".format(coil, fom1))
            self.data_dict[coil]['result'] = { 'filt_field' : 0 }

        logger.info("Coil #{} result: field = {}, res_freq = {}".format(coil,b_field,res_freq))

        return b_field

    def save_data(self):
        outpath = os.environ["HOME"] + "/GoogleDrive/Project8/Data/ESRData/Phase2/{:%Y%m%d_%H%M}/".format(datetime.now())
        if not os.path.exists(outpath):
            logger.info("Creating directory {}".format(outpath))
            os.makedirs(outpath)
        outfile = TFile(outpath+"esr.root", "recreate")

        from ROOT import MyStruct1, MyStruct2, MyStruct3
        struct1 = MyStruct1()
        struct2 = MyStruct2()
        struct3 = MyStruct3()

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
        struct1.fC4Polarity = int(insert['trap_coil_4_polarity'])
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
        struct1.fSStart = float(sweeper['hf_start_freq'])
        struct1.fSStop = float(sweeper['hf_stop_freq'])
        struct1.fSPower = float(sweeper['hf_power'])
        struct1.fSDwell = float(sweeper['hf_dwell_time'])
        struct1.fSNPts = int(sweeper['hf_n_sweep_points'])
        struct1.fSMode = sweeper['hf_freq_mode']
        struct1.fSOrder  = sweeper['hf_sweep_order']

        htree.Fill()
        htree.Write()

        rtree = TTree("result", "ESR scan results")
        for coil in range(1, 6):
            if coil not in self.data_dict:
                logger.warning("ESR coil #{} data not available".format(coil))
                continue
            pts = len(self.data_dict[coil]['raw_data']['frequency'])
            if pts != self.lockin_n_points:
                logger.warning("ESR coil #{}: unexpected trace length {}".format(coil, pts))
            dtree = TTree("coil{}".format(coil), "coil {} data".format(coil))
            dtree.Branch("raw", struct2, "freq/F:amp_x:amp_y")
            dtree.Branch("filt", AddressOf(struct2, "fF1"), "freq/F:result:target")

            for i in range(pts):
                struct2.fR1 = self.data_dict[coil]['raw_data']['frequency'][i]
                struct2.fR2 = self.data_dict[coil]['raw_data']['amp_x'][i]
                struct2.fR3 = self.data_dict[coil]['raw_data']['amp_y'][i]
                struct2.fF1 = self.data_dict[coil]['filtered_data']['freqs'][i]
                struct2.fF2 = self.data_dict[coil]['filtered_data']['result'][i]
                struct2.fF3 = self.data_dict[coil]['filtered_data']['target'][i]
                dtree.Fill()
            dtree.Write()

            if self.data_dict[coil]['result']['filt_field'] != 0:
                rbranch = rtree.Branch("coil{}".format(coil), struct3, "res_freq_Hz/F:b_field_T:b_field_e_T/F\
                                                                          :fit_field_T:fit_field_e_T")
                struct3.fCRF = self.data_dict[coil]['result']['res_freq']
                struct3.fCB = self.data_dict[coil]['result']['filt_field']
                struct3.fCBE = self.data_dict[coil]['result']['filt_field_e']
                struct3.fCFB = self.data_dict[coil]['result']['fit_field']
                struct3.fCFBE = self.data_dict[coil]['result']['fit_field_e']
                rbranch.Fill()
        rtree.Fill()
        rtree.Write()

        outfile.mkdir("Plots")
        outfile.cd("Plots")
        self.root_plot(outfile, outpath)
        self.field_plot(outfile, outpath)
        outfile.Close()


    def root_fits(self, raw_data, n_fits):

        data = numpy.column_stack((raw_data['frequency']*1e-6,
                                   raw_data['lockin_x_data']*1e6,
                                   raw_data['lockin_y_data']*1e6))
        data = data.ravel().view([('f','float'), ('x','float'), ('y','float')])
        fspan = data['f'][-1] - data['f'][0] + (self.hf_start_freq - self.hf_stop_freq) * 1e-6
        numpy.ndarray.sort(data)

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
        fe = numpy.array(len(data['f']) * [fspan / (len(data['f']) - 1) / 6.], dtype=float)
        f2e = numpy.concatenate((fe, fe))
        if b < (self.hf_start_freq + self.hf_stop_freq) / 2.:
            xe = numpy.array(len(data['x']) * [numpy.std(data['x'][-50:])])
            ye = numpy.array(len(data['y']) * [numpy.std(data['y'][-50:])])
        else:
            xe = numpy.array(len(data['x']) * [numpy.std(data['x'][:50])])
            ye = numpy.array(len(data['y']) * [numpy.std(data['y'][:50])])
        xye = numpy.concatenate((ye, xe))

        ct = 0
        while ct < n_fits:
            plot1 = TGraphErrors(len(f2), f2, xy, f2e, xye)
            plot1.Fit("gfit","ME")
            scale = (gfit.GetChisquare() / gfit.GetNDF())**0.5
            logger.info("Chi-Square : {} / {}; rescale error by {}".format(gfit.GetChisquare(), gfit.GetNDF(), scale))
            if scale > 0.95 and scale < 1.05:
                logger.info("Acceptable error reached, aborting iterative scale and fit")
            xe = xe * scale
            ye = ye * scale
            xye = xye * scale
            ct += 1

        plot1.SetName("xy_f")
        plot2 = TGraphErrors(len(data['f']), data['f']*1., data['y']*1., fe, ye)
        plot2.SetName("y_f")
        plot2.SetLineColor(2)
        gfit2 = TF1("gfit","-(x-[1])*gaus(0)-[3]", self.hf_start_freq*1e-6, self.hf_stop_freq*1e-6)
        gfit2.SetParameters(-gfit.GetParameter(4), gfit.GetParameter(1), gfit.GetParameter(2), gfit.GetParameter(5))
        gfit2.SetLineColor(3)

        ymax = max(numpy.max(data['x']), numpy.max(data['y']))
        ymin = min(numpy.min(data['x']), numpy.min(data['y']))
        yrng = ymax - ymin
        ymax += yrng/8.
        ymin -= yrng/8.
        plot2.GetYaxis().SetRangeUser(ymin, ymax)

        return { 'graph_xy' : plot1,
                 'graph_y' : plot2,
                 'fit' : gfit,
                 'fit_y': gfit2 }


    def root_plot(self, outfile, outpath):
        for coil in self.data_dict:
            can = TCanvas("can{}".format(coil), "coil{}".format(coil))
            self.data_dict[coil]['fits']['graph_y'].SetTitle("Coil {};Frequency (MHz);Amplitude (arb)".format(coil))
            self.data_dict[coil]['fits']['graph_y'].Draw("AL")
            self.data_dict[coil]['fits']['fit_y'].Draw("same")
            self.data_dict[coil]['fits']['graph_xy'].Draw("L")
            can.Write()
            can.SaveAs(outpath+"coil{}.pdf".format(coil))

    def field_plot(self, outfile, outpath):
        results = { coil : self.data_dict[coil]['result'] for coil in self.data_dict if (self.data_dict[coil]['result']['filt_field']!=0) }
        x = numpy.array([coil for coil in results], dtype=float)
        xe = numpy.zeros(len(x), dtype=float)
        y1 = numpy.array([results[coil]['filt_field'] for coil in results], dtype=float)
        y1e = numpy.array([results[coil]['filt_field_e'] for coil in results], dtype=float)
        y2 = numpy.array([results[coil]['fit_field'] for coil in results], dtype=float)
        y2e = numpy.array([results[coil]['fit_field_e'] for coil in results], dtype=float)

        can = TCanvas("can0", "field")
        g_filt = TGraphErrors(len(x), x, y1, xe, y1e)
        g_fit = TGraphErrors(len(x), x, y2, xe, y2e)
        g_fit.SetLineColor(2)
        mg = TMultiGraph()
        mg.Add(g_filt)
        mg.Add(g_fit)
        mg.SetTitle("Field Map;ESR Coil Position;Field (T)")
        mg.Draw("AL")
        can.Write()
        can.SaveAs(outpath+"fieldmap.pdf")

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
                               Float_t fR1;\
                               Float_t fR2;\
                               Float_t fR3;\
                               Float_t fF1;\
                               Float_t fF2;\
                               Float_t fF3;\
	                   };");
        gROOT.ProcessLine("struct MyStruct3 {\
                               Float_t fCRF;\
                               Float_t fCB;\
                               Float_t fCBE;\
                               Float_t fCFB;\
                               Float_t fCFBE;\
                           };");


    def run_scan(self, config_instruments=True, restore_defaults=True, coils=[1,2,3,4,5], n_fits=2, **kwargs):
        logger.info(kwargs)
        self.data_dict = {}
        if config_instruments:
            self.configure_instruments(restore_defaults)
        for i in coils:
            self.single_measure(i, n_fits)
        self.save_data()
        #logger.info(self.data_dict)
        self.reset_configure()
        return { coil : self.data_dict[coil]['result']['filt_field'] for coil in self.data_dict }


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


def WeinerFilter(freq_data, amp_data, shape='gaussian'):
    logger.info('doing filter on target: {}'.format(shape))
    data = zip(freq_data, amp_data)
    data.sort()
    f,v= zip(*data)
    frequencies = numpy.array(f, dtype=float)
    voltages = numpy.array(v, dtype=complex)
    width = (frequencies[numpy.argmin(voltages)] - frequencies[numpy.argmax(voltages)]) / 2.
    x1 = (frequencies - frequencies[0])
    x2 = (frequencies - frequencies[-1])
    if shape == 'gaussian':
        deriv1 = -x1 * numpy.exp(-x1**2 / 2. / width**2) * numpy.exp(0.5) / width
        deriv2 = -x2 * numpy.exp(-x2**2 / 2. / width**2) * numpy.exp(0.5) / width
    elif shape == 'lorentzian':
        deriv1 = -x1 / (x1**2 + (width * 3.**0.5)**2)**2 * 16. * width**3
        deriv2 = -x2 / (x2**2 + (width * 3.**0.5)**2)**2 * 16. * width**3
    target_signal = numpy.concatenate((deriv1[:len(deriv1)/2], deriv2[len(deriv2)/2:]))
    if not sum(target_signal != 0):
        raise ValueError("target signal identically 0, did you give width in Hz?")
    data_fft = numpy.fft.fft(voltages)
    data_fft[0] = 0
    target_fft = numpy.fft.fft(target_signal)
    filtered = numpy.fft.ifft(data_fft * target_fft)
    return {'freqs': frequencies,
            'result': numpy.abs(filtered),
            'target': target_signal,
           }
