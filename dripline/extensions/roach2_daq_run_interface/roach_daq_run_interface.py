'''
'''

from __future__ import absolute_import


# standard imports
import logging
import time
import os
# internal imports
from dripline import core
from .daq_run_interface import DAQProvider

__all__ = []

logger = logging.getLogger(__name__)

__all__.append('ROACH1ChAcquisitionInterface')
class ROACH1ChAcquisitionInterface(DAQProvider):
    '''
    A DAQProvider for interacting with ROACH-Psyllid DAQ
    '''
    def __init__(self,
                 channel = None,
                 psyllid_interface = 'psyllid_interface',
                 daq_target = 'roach2_interface',
                 hf_lo_freq = None,
                 mask_target_path = None,
                 default_trigger_dict = None,
                 **kwargs
                ):

        DAQProvider.__init__(self, **kwargs)

        self.psyllid_interface = psyllid_interface
        self.daq_target = daq_target
        self.status_value = None
        self.channel_id = channel
        self.freq_dict = {self.channel_id: None}
        self._run_time = 1
        self._run_name = "test"
        self.mask_target_path = mask_target_path
        self.payload_channel = {'channel':self.channel_id}
        self.default_trigger_dict = default_trigger_dict

        if hf_lo_freq is None:
            raise core.ThrowReply('DriplineValueError', 'The roach daq run interface interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq

        if mask_target_path is None:
            logger.warning('No mask target path set. Triggered data taking not possible.')

    def prepare_daq_system(self):
        '''
        Checks psyllid and roach
        Checks acquisition mode
        Gets roach frequency and sets psyllid frequency
        '''
        logger.info('Doing setup checks...')
        self._check_psyllid_instance()

        acquisition_mode = self.acquisition_mode
        logger.info('Psyllid instance for this channel is in acquisition mode: {}'.format(acquisition_mode))

        if self._check_roach2_is_ready() == False:
            logger.warning('ROACH2 check indicates ADC is not calibrated.')

        logger.info('Setting Psyllid central frequency identical to ROACH2 central frequency')
        freqs = self._get_roach_central_freqs()
        self.central_frequency = freqs[self.channel_id]


    def _check_roach2_is_ready(self):
        '''
        Asks roach2_interface whether roach is running and adc is calibrated
        '''
        logger.info('Checking ROACH2 status')
        result = self.get(endpoint=self.daq_target, specifier='is_running')
        if result==True:
            result = self.get(endpoint=self.daq_target, specifier='calibration_status')
            if result == True:
                logger.info('ROACH2 is running and ADCs are calibrated')
                return True
            else:
                logger.info('ROACH2 is running but ADC has not been calibrated')
                # For now this does not prevent data taking, because the roach2_interface cannot now whether the calibration was successful or not
                # the calibration status is therefore only semi meaningful
                return True
        else:
            logger.error('ROACH2 is not ready')
            raise core.ThrowReply('DriplineGenericDAQError', 'ROACH2 is not ready')


    def _check_psyllid_instance(self):
        '''
        Checks psyllid instance is running and matches channel settings
        Activates psyllid if deactivated
        Checks channel and stream labels are matching
        '''
        logger.info('Checking Psyllid service & instance')

        self.status_value = self.cmd(endpoint=self.psyllid_interface, specifier='request_status', keyed_args = self.payload_channel)

        if self.status_value == 0:
            self.cmd(endpoint=self.psyllid_interface, specifier='activate', keyed_args = self.payload_channel)
            self.status_value = self.cmd(endpoint=self.psyllid_interface, specifier='request_status', keyed_args = self.payload_channel)


    @property
    def is_running(self):
        '''
        Requests status of psyllid
        Returns True if status is 5 (currently taking data)
        '''
        result = self.cmd(endpoint=self.psyllid_interface, specifier='request_status', keyed_args = self.payload_channel, timeout_s=10)
        self.status_value = result
        logger.info('psyllid status is {}'.format(self.status_value))
        if self.status_value==5:
            return True
        else:
            return False

    def _do_checks(self):
        '''
        Checks everything that could prevent a successful run (in theory)
        '''
        if self._run_time ==0:
            raise core.ThrowReply('DriplineValueError', 'run time is zero')

        #checking that no run is in progress
        if self.is_running == True:
            raise core.ThrowReply('DriplineGenericDAQError', 'Psyllid is already running')

        self._check_psyllid_instance()

        if self.status_value!=4:
            raise core.ThrowReply('DriplineGenericDAQError', 'Psyllid DAQ is not activated')

        # check psyllid is ready to write a file
        result = self.cmd(endpoint=self.psyllid_interface, specifier='is_psyllid_using_monarch', keyed_args = self.payload_channel)
        if result != True:
            raise core.ThrowReply('DriplineGenericDAQError', 'Psyllid is not using monarch and therefore not ready to write a file')

        # checking roach is ready
        if self._check_roach2_is_ready() != True:
            raise core.ThrowReply('DriplineGenericDAQError', 'ROACH2 is not ready. ADC not calibrated.')

        # check channel is unblocked
        blocked_channels = self.get(endpoint=self.daq_target, specifier='blocked_channels')
        if self.channel_id in blocked_channels:
            raise core.ThrowReply('DriplineGenericDAQError', 'Channel is blocked')

        # check frequency matches
        roach_freqs = self._get_roach_central_freqs()
        psyllid_freq = self._get_psyllid_central_freq()
        if abs(roach_freqs[self.channel_id]-psyllid_freq)>1:
            logger.error('Frequency mismatch: roach cf is {}Hz, psyllid cf is {}Hz'.format(roach_freqs[self.channel_id], psyllid_freq))
            raise core.ThrowReply('DriplineGenericDAQError', 'Frequency mismatch')


        return "checks successful"


    def determine_RF_ROI(self):
        '''
        Sets frequency information in _run_metadata
        '''
        logger.info('trying to determine roi')

        rf_input = self.get(endpoint=self._hf_lo_freq['endpoint_name'])[self._hf_lo_freq['payload_field']]
        logger.debug('{} returned {}'.format(self._hf_lo_freq['endpoint_name'],rf_input))
        hf_lo_freq = float(self._hf_lo_freq['calibration'][rf_input])
        self._run_meta['RF_HF_MIXING'] = hf_lo_freq
        logger.debug('RF High stage mixing: {}'.format(hf_lo_freq))

        logger.info('Getting central frequency from ROACH2')
        cfs = self._get_roach_central_freqs()
        cf = cfs[self.channel_id]
        logger.info('Central frequency is: {}'.format(cf))

        self._run_meta['RF_ROI_MIN'] = float(cf-50e6) + hf_lo_freq
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

        self._run_meta['RF_ROI_MAX'] = float(cf+50e6) + hf_lo_freq
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))


    def _start_data_taking(self, directory, filename):
        '''
        Blocks roach channel
        Converts seconds to miliseconds
        Creates directory for data files
        Tells psyllid_provider to tell psyllid to start the run
        Unblocks roach channels if that fails
        '''

        setup = { 'roach' : self.get(endpoint=self.daq_target, specifier='registers') }
        psyllid_config_kwargs = {
                                  'endpoint' : self.psyllid_interface,
                                  'specifier' : 'get_active_config',
                                  'keyed_args' : { 'channel' : self.channel_id,
                                                'key' : 'prf' }
                                }
        setup.update( { 'psyllid' :
                            { 'prf' : self.cmd(**psyllid_config_kwargs) } } )

        if self.acquisition_mode == 'triggering':
            payload = {'channel':self.channel_id, 'filename':'{}/{}_mask.yaml'.format(directory,filename)}
            self.cmd(endpoint=self.psyllid_interface, specifier='_write_trigger_mask', payload=payload)
            for key in ('fmt', 'tfrr', 'eb'):
                psyllid_config_kwargs['payload'].update( { 'key' : key } )
                setup['psyllid'].update( { key : self.cmd(**psyllid_config_kwargs) } )
        self._send_metadata( type='setup', data=setup)

        logger.info('block roach channel')
        self.cmd(endpoint=self.daq_target, specifier='block_channel', keyed_args = self.payload_channel)

        # switching from seconds to milisecons
        duration = self._run_time*1000.0
        logger.info('run duration in ms: {}'.format(duration))

        psyllid_filename = filename+'.egg'

        logger.info('Going to tell psyllid to start the run')
        payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':duration}
        try:
            self.cmd(endpoint=self.psyllid_interface, specifier='start_run', keyed_args = payload)
        except core.ThrowReply as e:
            logger.critical('Error from psyllid provider or psyllid. Starting psyllid run failed.')
            payload = {'channel': self.channel_id}
            try:
                self.cmd(endpoint=self.daq_target, specifier='unblock_channel', keyed_args = payload)
                logger.info('Unblocked channel')
            finally:
                raise e
        except Exception as e:
            logger.critical('Something else went wrong.')
            payload = {'channel': self.channel_id}
            try:
                self.cmd(endpoint=self.daq_target, specifier='unblock_channel', keyed_args = payload)
                logger.info('Unblocked channel')
            finally:
                raise e


    def _stop_data_taking(self):
        '''
        Checks whether psyllid run has stopped
        If it hasn't, stops run
        Unblocks roach channel no matter what
        '''
        try:
            if self.is_running:
                logger.info('Psyllid still running. Telling it to stop the run')
                self.cmd(endpoint=self.psyllid_interface, specifier='stop_run', keyed_args = self.payload_channel)
        except core.ThrowReply as e:
            logger.critical('Getting Psyllid status or stopping run failed')
            logger.info('Unblock channel')
            payload = {'channel': self.channel_id}
            try:
                self.cmd(endpoint=self.daq_target, specifier='unblock_channel', keyed_args = payload)
            finally:
                raise e
        except Exception as e:
            logger.critical('Something else went wrong')
            payload = {'channel': self.channel_id}
            try:
                self.cmd(endpoint=self.daq_target, specifier='unblock_channel', keyed_args = payload)
            finally:
                raise e
        else:
            logger.info('Unblock channel')
            payload = {'channel': self.channel_id}
            self.cmd(endpoint=self.daq_target, specifier='unblock_channel', keyed_args = payload)


    def stop_psyllid(self):
        '''
        Makes psyllid exit and unblocks roach channel
        '''
        self.cmd(endpoint=self.psyllid_interface, specifier='quit_psyllid', keyed_args = self.payload_channel)
        self.cmd(endpoint=self.daq_target, specifier='unblock_channel', keyed_args = self.payload_channel)


    ###########################
    # frequency sets and gets #
    ###########################

    def _get_roach_central_freqs(self):
        result = self.get(endpoint=self.daq_target, specifier='all_central_frequencies')
        logger.info('ROACH central freqs {}'.format(result))
        return result


    def _get_psyllid_central_freq(self):
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_central_frequency', keyed_args = self.payload_channel)
        logger.info('Psyllid central freqs {}'.format(result))
        return result


    @property
    def central_frequency(self):
        return self.freq_dict[self.channel_id]


    @central_frequency.setter
    def central_frequency(self, cf):
        '''
        Sets central frequency in roach channel
        roach2_interface returns true frequency (can deviate from requested cf)
        Sets same frequency in psyllid instance
        '''
        payload = {'cf':float(cf), 'channel':self.channel_id}
        result = self.cmd(endpoint=self.daq_target, specifier='set_central_frequency', keyed_args = payload)
        logger.info('The roach central frequency is now {}Hz'.format(result))

        self.freq_dict[self.channel_id]=round(result)
        payload = {'cf':self.freq_dict[self.channel_id], 'channel':self.channel_id}
        self.cmd(endpoint=self.psyllid_interface, specifier='set_central_frequency', keyed_args = payload)


    ###################
    # trigger control #
    ###################

    @property
    def acquisition_mode(self):
        '''
        The Cmd returns a dictionary like {"mode": "someMode"}; we want just the mode value.
        '''
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_acquisition_mode', keyed_args = self.payload_channel)['mode']
        return result

    @acquisition_mode.setter
    def acquisition_mode(self, x):
        raise core.ThrowReply('DriplineGenericDAQError', 'acquisition mode cannot be set via dragonfly')


    @property
    def threshold_type(self):
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_threshold_type', keyed_args = self.payload_channel)
        return result

    @threshold_type.setter
    def threshold_type(self, snr_or_sigma):
        self.cmd(endpoint=self.psyllid_interface, specifier='set_threshold_type', keyed_args = {'channel': self.channel_id, 'snr_or_sigma': snr_or_sigma})


    @property
    def threshold(self):
        if self.threshold_type == 'snr':
            return self.cmd(endpoint=self.psyllid_interface, specifier='get_fmt_snr_threshold', keyed_args = self.payload_channel)
        else:
            return self.cmd(endpoint=self.psyllid_interface, specifier='get_fmt_sigma_threshold', keyed_args = self.payload_channel)

    @threshold.setter
    def threshold(self, threshold):
        if self.threshold_type == 'snr':
            self.cmd(endpoint=self.psyllid_interface, specifier='set_fmt_snr_threshold', keyed_args = {'channel': self.channel_id, 'threshold': threshold})
        else:
            self.cmd(endpoint=self.psyllid_interface, specifier='set_fmt_sigma_threshold', keyed_args = {'channel': self.channel_id, 'threshold': threshold})
        self.cmd(endpoint=self.psyllid_interface, specifier='set_trigger_mode', keyed_args = self.payload_channel)


    @property
    def high_threshold(self):
        if self.threshold_type == 'snr':
            return self.cmd(endpoint=self.psyllid_interface, specifier='get_fmt_snr_high_threshold', keyed_args = self.payload_channel)
        else:
            return self.cmd(endpoint=self.psyllid_interface, specifier='get_fmt_sigma_high_threshold', keyed_args = self.payload_channel)

    @high_threshold.setter
    def high_threshold(self, threshold):
        if self.threshold_type == 'snr':
            self.cmd(endpoint=self.psyllid_interface, specifier='set_fmt_snr_high_threshold', keyed_args = {'channel': self.channel_id, 'threshold': threshold})
        else:
            self.cmd(endpoint=self.psyllid_interface, specifier='set_fmt_sigma_high_threshold', keyed_args = {'channel': self.channel_id, 'threshold': threshold})
        self.cmd(endpoint=self.psyllid_interface, specifier='set_trigger_mode', keyed_args = self.payload_channel)


    @property
    def n_triggers(self):
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_n_triggers', keyed_args = self.payload_channel)
        return result

    @n_triggers.setter
    def n_triggers(self, n_triggers):
        self.cmd(endpoint=self.psyllid_interface, specifier='set_n_triggers', keyed_args = {'channel': self.channel_id, 'n_triggers': n_triggers})


    @property
    def pretrigger_time(self):
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_pretrigger_time', keyed_args = self.payload_channel)
        return result

    @pretrigger_time.setter
    def pretrigger_time(self, pretrigger_time):
        '''
        Psyllid only adopts change of pretrigger time after reactivation
        '''
        self.cmd(endpoint=self.psyllid_interface, specifier='set_pretrigger_time', keyed_args = {'channel': self.channel_id, 'pretrigger_time': pretrigger_time})
        self.cmd(endpoint=self.psyllid_interface, specifier='save_reactivate', keyed_args = self.payload_channel)


    @property
    def skip_tolerance(self):
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_skip_tolerance', keyed_args = self.payload_channel)
        return result

    @skip_tolerance.setter
    def skip_tolerance(self, skip_tolerance):
        '''
        Psyllid only adopts change of skip tolerance after reactivation
        '''
        self.cmd(endpoint=self.psyllid_interface, specifier='set_skip_tolerance', keyed_args = {'channel': self.channel_id, 'skip_tolerance': skip_tolerance})
        self.cmd(endpoint=self.psyllid_interface, specifier='save_reactivate', keyed_args = self.payload_channel)


    @property
    def trigger_type(self):
        '''
        Returns the kind of trigger that is currently set
        '''
        n_triggers = self.cmd(endpoint=self.psyllid_interface, specifier='get_n_triggers', keyed_args = self.payload_channel)
        trigger_mode = self.cmd(endpoint=self.psyllid_interface, specifier='get_trigger_mode', keyed_args = self.payload_channel)

        if n_triggers > 1:
            trigger_type = 'multi-trigger'
        else:
            trigger_type = trigger_mode

        return trigger_type

    @trigger_type.setter
    def trigger_type(self, x):
        raise core.ThrowReply('DriplineGenericDAQError', 'Trigger type is result of trigger settings and cannot be set directly')


    @property
    def trigger_settings(self):
        '''
        Returns all trigger settings
        '''
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_trigger_configuration', keyed_args = self.payload_channel)
        return result


    @trigger_settings.setter
    def trigger_settings(self, x):
        raise core.ThrowReply('DriplineGenericDAQError', 'Use configure_trigger command to set all trigger parameters at once')


    def configure_trigger(self, threshold, high_threshold, n_triggers):
        '''
        Set all trigger parameters with one command
        '''
        payload = {'threshold' : threshold, 'threshold_high' : high_threshold, 'n_triggers' : n_triggers, 'channel' : self.channel_id}
        self.cmd(endpoint=self.psyllid_interface, specifier='set_trigger_configuration', keyed_args = payload)


    @property
    def time_window_settings(self):
        '''
        Returns pretrigger time and skip tolerance
        '''
        result = self.cmd(endpoint=self.psyllid_interface, specifier='get_time_window', keyed_args = self.payload_channel)
        return result


    @time_window_settings.setter
    def time_window_settings(self, x):
        raise core.ThrowReply('DriplineGenericDAQError', 'Use configure_time_window command to set skip_tolerance and pretrigger_time')


    def configure_time_window(self, pretrigger_time, skip_tolerance):
        '''
        Set pretrigger time and skip tolerance with one command
        '''
        payload =  {'skip_tolerance': skip_tolerance, 'pretrigger_time': pretrigger_time, 'channel' : self.channel_id}
        self.cmd(endpoint=self.psyllid_interface, specifier='set_time_window', keyed_args = payload)


    @property
    def default_trigger_settings(self):
        '''
        Returns dictionary containing default trigger settings
        '''
        if self.default_trigger_dict == None:
            raise core.ThrowReply('DriplineGenericDAQError', 'No default trigger settings present')
        else:
            return self.default_trigger_dict

    @default_trigger_settings.setter
    def default_trigger_settings(self, x):
        raise core.ThrowReply('DriplineGenericDAQError', 'Default settings must be specified in config file. Use cmd set_default_trigger to apply default settings')


    def set_default_trigger(self):
        '''
        Sets trigger parameters to values specified in config
        '''
        if self.default_trigger_dict == None:
            raise core.ThrowReply('DriplineGenericDAQError', 'No default trigger settings present')
        else:
            self.threshold_type = self.default_trigger_dict['threshold_type']
            self.configure_trigger(threshold=self.default_trigger_dict['threshold'], high_threshold=self.default_trigger_dict['high_threshold'], n_triggers=self.default_trigger_dict['n_triggers'])
            self.configure_time_window(pretrigger_time=float(self.default_trigger_dict['pretrigger_time']), skip_tolerance=float(self.default_trigger_dict['skip_tolerance']))


    def make_trigger_mask(self):
        '''
        Acquire and save new mask
        Raises exception if no mask_target_path was not set in config file
        '''
        if self.mask_target_path == None:
            raise core.ThrowReply('DriplineGenericDAQError', 'No target path set for trigger mask')

        timestr = time.strftime("%Y%m%d_%H%M%S")
        filename = '{}_frequency_mask_channel_{}_cf_{}.yaml'.format(timestr, self.channel_id, self.freq_dict[self.channel_id])
        path = os.path.join(self.mask_target_path, filename)
        payload = {'channel':self.channel_id, 'filename':path}
        self.cmd(endpoint=self.psyllid_interface, specifier='make_trigger_mask', keyed_args = payload)
