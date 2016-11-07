from __future__ import absolute_import
__all__ = []

import os
import numpy
import logging
import json
from datetime import datetime
from time import sleep, time

from dripline import core

logger = logging.getLogger(__name__)


__all__.append('ESR_Measurement')
@core.fancy_doc
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
        self.hf_start_freq = self._default_hf_start_freq = hf_start_freq
        self.hf_stop_freq = self._default_hf_stop_freq = hf_stop_freq
        self.hf_power = self._default_hf_power = hf_power
        self.hf_n_sweep_points = self._default_hf_n_sweep_points = hf_n_sweep_points
        self.hf_dwell_time = self._default_hf_dwell_time = hf_dwell_time
        # Output storage
        self.output_dict = {}


    def run_scan(self, config_instruments=True, restore_defaults=True, coils=[1,2,3,4,5], n_fits=2, **kwargs):
        '''
        Wraps all ESR functionality into single method call with tunable arguments.
        This function should interface with run_scripting through the action_esr_run method.
        '''
        logger.info(kwargs)
        self.output_dict = {}
        if config_instruments:
            self.configure_instruments(restore_defaults)
        self.capture_settings()
        for i in coils:
            self.single_measure(i)
        if config_instruments:
            self.reset_configure()
            # FIXME: warning to user to reset_configure manually if not performed here
        outfile = self.save_data()
        return "ESR data file created: {}".format(outfile)


    def configure_instruments(self, reset):
        '''
        Configure instruments to default settings.
        '''
        if reset:
            self.restore_presets()
        # lockin controls
        self.check_endpoint('lockin_n_points', self.lockin_n_points)
        self.check_endpoint('lockin_sampling_interval', self.lockin_sampling_interval)
        self.check_endpoint('lockin_trigger', self.lockin_trigger)
        self.check_endpoint('lockin_curve_mask', self.lockin_curve_mask)
        self.check_endpoint('lockin_srq_mask', self.lockin_srq_mask)
        self.check_endpoint('lockin_osc_amp', self.lockin_osc_amp)
        self.check_endpoint('lockin_osc_freq', self.lockin_osc_freq)
        #self.check_endpoint('lockin_ac_gain', self.lockin_ac_gain) # Lockin settings currently bind ACGAIN to SEN parameter
        self.check_endpoint('lockin_sensitivity', self.lockin_sensitivity)
        self.check_endpoint('lockin_time_constant', self.lockin_time_constant)
        # sweeper controls
        while True:
            err_msg = self.raw_get_endpoint('hf_error_check')
            if err_msg == '+0,"No error"':
                break
            logger.warning("Clearing sweeper error queue: {}".format(err_msg))
        self.check_endpoint('hf_output_status', 0)
        self.check_endpoint('hf_freq_mode', 'LIST')
        self.check_endpoint('hf_sweep_order', str(self.hf_sweep_order))
        self.check_endpoint('hf_start_freq', float(self.hf_start_freq))
        self.check_endpoint('hf_stop_freq', float(self.hf_stop_freq))
        self.check_endpoint('hf_power', self.hf_power)
        self.check_endpoint('hf_n_sweep_points', self.hf_n_sweep_points)
        self.check_endpoint('hf_dwell_time', self.hf_dwell_time)
        err_msg = self.raw_get_endpoint('hf_error_check')
        if err_msg != '+0,"No error"':
            raise core.exceptions.DriplineHardwareError("Sweeper error: {}".format(err_msg))
        # relays
        self.check_endpoint('esr_tickler_switch', 1)
        for coil in range(1, 6):
            self.check_endpoint('esr_coil_{}_switch_status'.format(coil), 0)

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
        Immutable "safe" configuration for switches and sweeper for after ESR scan
        '''
        self.check_endpoint('hf_output_status', 0)
        self.check_endpoint('hf_power', -50)
        self.check_endpoint('esr_tickler_switch', 1)
        for coil in range(1, 6):
            self.check_endpoint('esr_coil_{}_switch_status'.format(coil), 0)

    def capture_settings(self):
        '''
        Record current status of the insert, lockin, and sweeper before ESR scan
        FIXME: Endpoints should either be locked here or already
        '''
        settings = {}
        settings['insert'] = self.raw_get_endpoint("run_metadata", timeout=20)
        settings['lockin'] = self.raw_get_endpoint("lockin_settings", timeout=20)
        settings['sweeper'] = self.raw_get_endpoint("sweeper_settings")
        self.output_dict.update({'header' : settings})

    def single_measure(self, coil):
        '''
        Communicate with lockin, sweeper, and switches to execute single ESR coil scan.
        Data is retrieved but not analyzed.
        '''
        self.check_endpoint('hf_output_status', 1)
        self.check_endpoint('esr_coil_{}_switch_status'.format(coil), 1)
        starttime = time()
        self.raw_get_endpoint('lockin_take_data')
        # HF sweep takes 60 sec
        while True:
            status = self.raw_get_endpoint('lockin_curve_status')
            logger.info(status)
            if status.split(',')[0] == '0':
                break
            else:
                time_est = min( 5, (self.lockin_n_points-int(status.split(',')[3]))*self.lockin_sampling_interval*1e-3 )
                logger.info("sleeping for {} sec".format(time_est))
                sleep(time_est)
        self.check_endpoint('hf_output_status', 0)
        self.check_endpoint('esr_coil_{}_switch_status'.format(coil), 0)

        # Get the lockin data
        raw = { 'adc' : self.pull_lockin_data('adc'),
                'x' : self.pull_lockin_data('x'),
                'y' : self.pull_lockin_data('y') }
        self.output_dict.update( { 'coil{}'.format(coil) : { 'data' : raw,
                                                             'time' : starttime } } )

    def save_data(self):
        '''
        Save data to output json file
        '''
        outpath = "/data/secondary/esr/raw/{:%Y%m%d_%H%M%S}/".format(datetime.now())
        if not os.path.exists(outpath):
            logger.info("Creating directory {}".format(outpath))
            os.makedirs(outpath)
        fp = open(outpath+"esr.json", "w")
        json.dump(obj=self.output_dict, fp=fp, indent=4)
        fp.close()
        return outpath+"esr.json"


    def pull_lockin_data(self, key):
        result = self.provider.cmd(target="lockin_interface", method_name="grab_data", value=[key], timeout=20)
        return result['values'][0].replace('\x00','')

    def raw_get_endpoint(self, endptname, **kwargs):
        result = self.provider.get(target=endptname, **kwargs)
        return result['value_raw']

    def check_endpoint(self, endptname, val):
        if not isinstance(val, (int,float,str,unicode)):
            logger.warning("set value is of type {} with value {}, cannot process".format(type(val), val))
            raise TypeError
        result = self.provider.set(target=endptname, value=val)
        if 'values' in result:
            result = result['values'][0]
        elif 'value_raw' in result:
            result = result['value_raw']
        if isinstance(val, (int,float)):
            result = float(result)
        if result != val:
            raise core.exceptions.DriplineValueError("Failure to set endpoint: {}".format(endptname))
        return
