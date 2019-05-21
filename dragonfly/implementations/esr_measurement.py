'''
A service for interfacing with the ESR
'''

from __future__ import absolute_import
__all__ = []

import six
import os
import logging
import json
from datetime import datetime
from time import sleep, time

from dripline import core

logger = logging.getLogger(__name__)


__all__.append('ESR_Measurement')
@core.fancy_doc
class ESR_Measurement(core.Endpoint):
    '''
    Operate the ESR system to measure the B-field off-axis.
    Methods are sorted by order of call within run_scan.
    '''
    def __init__(self,
                 **kwargs):
        core.Endpoint.__init__(self,**kwargs)
        # Settings for lockin and sweeper
        self.lockin_n_points = None
        self.lockin_sampling_interval = None
        # Output storage
        self.output_dict = {}


    def run_scan(self, config_instruments=True, coils=[1,2,3,4,5], n_fits=2, **kwargs):
        '''
        Wraps all ESR functionality into single method call with tunable arguments.
        This function should interface with run_scripting through the action_esr_run method.

        config_instruments (bool): flag to configure instruments
        coils (list): list of coil numbers (int) for ESR scan
        n_fits (int): number of fits to perform
        '''
        logger.info(kwargs)
        self.output_dict = {}
        if config_instruments:
            self.configure_instruments()
        self.capture_settings()
        for i in coils:
            self.single_measure(i)
        if config_instruments:
            self.reset_configure()
            # FIXME: warning to user to reset_configure manually if not performed here
        outfile = self.save_data()
        return "ESR data file created: {}".format(outfile)


    def configure_instruments(self):
        '''
        Configure instruments to default settings.
        '''
        self.provider.set('lockin_esr_settings',1,timeout=20)
        err_msg = self.raw_get_endpoint('hf_error_check')
        if not err_msg ==  '+0,"No error"':
            logger.warning("Clearing sweeper error queue: {}".format(err_msg))
        self.provider.set('sweeper_esr_settings',1)
        # relays
        self.check_endpoint('esr_tickler_switch', 1)
        for coil in range(1, 6):
            self.check_endpoint('esr_coil_{}_switch_status'.format(coil), 0)

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
        self.lockin_n_points = int(settings['lockin']['lockin_n_points'])
        self.lockin_sampling_interval = int(settings['lockin']['lockin_sampling_interval'])
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
        tstamp = datetime.now()
        outpath = "/data/secondary/esr/raw/{0:%Y}/{0:%m%d}/{0:%Y%m%d_%H%M%S}/".format(tstamp)
        if not os.path.exists(outpath):
            logger.info("Creating directory {}".format(outpath))
            os.makedirs(outpath)
        else:
            raise exceptions.DriplineInternalError("Output directory already exists!")
        outfile = outpath+"{:%Y%m%d_%H%M%S}-esr.json".format(tstamp)
        fp = open(outfile, "w")
        json.dump(obj=self.output_dict, fp=fp, indent=4)
        fp.close()
        return outfile


    def pull_lockin_data(self, key):
        '''
        Call grab_data method of lockin_interface give key

        key (): #TODO_DOC
        '''
        result = self.provider.cmd(target="lockin_interface", method_name="grab_data", value=[key], timeout=20)
        return result['values'][0].replace('\x00','')

    def raw_get_endpoint(self, endptname, **kwargs):
        '''
        Get raw value of endpoint

        endptname (str): name of endpoint
        '''
        result = self.provider.get(target=endptname, **kwargs)
        return result['value_raw']

    def check_endpoint(self, endptname, val):
        '''
        Sets endpoint to value

        endptname (str): name of endpoint
        val (int,float,str): value of endpoint to set
        '''
        if not isinstance(val, (int,float,six.string_types)):
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
