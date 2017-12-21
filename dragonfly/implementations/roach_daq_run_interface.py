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
                 psyllid_interface='psyllid_interface',
                 daq_target = 'roach2_interface',
                 hf_lo_freq = None,
                 mask_target_path = None,
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

        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('The roach daq run interface interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq

        if mask_target_path is None:
            logger.warning('No mask target path set. Triggered data taking not possible.')



    # checks psyllid and roach, checks acquisition mode, sets roach frequency to psyllid frequency
    def prepare_daq_system(self):
        logger.info('Doing setup checks...')
        self._check_psyllid_instance()

        # find out whether psyllid instante is in streaming or triggering mode
        acquisition_mode = self.provider.cmd(self.psyllid_interface, 'get_acquisition_mode', payload = self.payload_channel)
        logger.info('Psyllid instance for this channel is in acquisition mode: {}'.format(acquisition_mode['values'][0]))

        if self._check_roach2_is_ready() == False:
            logger.warning('ROACH2 check indicates ADC is not calibrated. Starting a run now will result in error')

        logger.info('Setting Psyllid central frequency identical to ROACH2 central frequency')
        freqs = self._get_roach_central_freqs()
        self.central_frequency = freqs[self.channel_id]


    # asks roach2_interface whether roach is running and adc is calibrated
    def _check_roach2_is_ready(self):
        logger.info('Checking ROACH2 status')
        #call is_running from roach2_interface
        result = self.provider.get(self.daq_target+ '.is_running')['values'][0]
        if result==True:
            result = self.provider.get(self.daq_target+'.calibration_status')['values'][0]
            if result == True:
                logger.info('ROACH2 is running and ADCs are calibrated')
                return True
            else:
                logger.info('ROACH2 is running but ADC has not been calibrated')
                return False
        else:
            logger.error('ROACH2 is not running')
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not running')


    # checks psyllid instance is running and matches channel settings
    # activates psyllid if deactivates
    def _check_psyllid_instance(self):
        logger.info('Checking Psyllid service & instance')

        # check psyllid is responding by requesting status
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)['values'][0]

        # activate psyllid if deactivated
        if self.status_value == 0:
            self.provider.cmd(self.psyllid_interface, 'activate', payload = self.payload_channel)
            self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)['values'][0]

        #check channel match
        active_channels = self.provider.get(self.psyllid_interface + '.active_channels')
        logger.info(active_channels)
        if self.channel_id in active_channels==False:
            logger.error('The Psyllid and ROACH2 channel interfaces do not match')
            raise core.exceptions.DriplineGenericDAQError('The Psyllid and ROACH channel interfaces do not match')


    # requests status of psyllid
    # returns True if status is 5
    @property
    def is_running(self):
        result = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel, timeout=10)
        self.status_value = result['values'][0]
        logger.info('psyllid status is {}'.format(self.status_value))
        if self.status_value==5:
            return True
        else:
            return False

    # checks everything that could prevent a successful run (in theory)
    def _do_checks(self):
        if self._run_time ==0:
            raise core.exceptions.DriplineValueError('run time is zero')

        #checking that no run is in progress
        if self.is_running == True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is already running')

        self._check_psyllid_instance()

        if self.status_value!=4:
            raise core.exceptions.DriplineGenericDAQError('Psyllid DAQ is not activated')

        # check psyllid is ready to write a file
        result = self.provider.cmd(self.psyllid_interface, 'is_psyllid_using_monarch', payload = self.payload_channel)['values'][0]
        if result != True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not using monarch and therefore not ready to write a file')

        #checking roach is ready
        if self._check_roach2_is_ready() != True:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not ready. ADC not calibrated.')

        # check channel is unblocked
        blocked_channels = self.provider.get(self.daq_target+ '.blocked_channels')
        if self.channel_id in blocked_channels: 
            raise core.exceptions.DriplineGenericDAQError('Channel is blocked')

        #check frequency matches
        roach_freqs = self._get_roach_central_freqs()
        psyllid_freq = self._get_psyllid_central_freq()
        if abs(roach_freqs[self.channel_id]-psyllid_freq)>1:
            logger.error('Frequency mismatch: roach cf is {}Hz, psyllid cf is {}Hz'.format(roach_freqs[self.channel_id], psyllid_freq))
            raise core.exceptions.DriplineGenericDAQError('Frequency mismatch')

        return "checks successful"


    # sets frequency information in _run_metadata
    def determine_RF_ROI(self):
        logger.info('trying to determine roi')

        self._run_meta['RF_HF_MIXING'] = float(self._hf_lo_freq)
        logger.debug('RF High stage mixing: {}'.format(self._run_meta['RF_HF_MIXING']))

        logger.info('Getting central frequency from ROACH2')
        cfs = self._get_roach_central_freqs()
        cf = cfs[self.channel_id]
        logger.info('Central frequency is: {}'.format(cf))

        self._run_meta['RF_ROI_MIN'] = float(cf-50e6) + float(self._hf_lo_freq)
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

        self._run_meta['RF_ROI_MAX'] = float(cf+50e6) + float(self._hf_lo_freq)
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))


    # blocks roach channel
    # converts seconds to miliseconds
    # creates directory for data files
    # tells psyllid_provider to tell psyllid to start the run
    # unblocks roach channels if that fails
    # sets run time in _stop_handle for end of run
    def _start_data_taking(self, directory, filename):
        logger.info('block roach channel')
        self.provider.cmd(self.daq_target, 'block_channel', payload = self.payload_channel)

        # switching from seconds to milisecons
        duration = self._run_time*1000.0
        logger.info('run duration in ms: {}'.format(duration))

        psyllid_filename = filename+'.egg'
        if not os.path.exists(directory):
            os.makedirs(directory)

        logger.info('Going to tell psyllid to start the run')
        payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':duration}
        try:
            self.provider.cmd(self.psyllid_interface, 'start_run', payload = payload)
        except core.exceptions.DriplineError as e:
            logger.critical('Error from psyllid provider or psyllid. Starting psyllid run failed.')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
                logger.info('Unblocked channel')
            finally:
                raise e
        except Exception as e:
            logger.critical('Something else went wrong.')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
                logger.info('Unblocked channel')
            finally:
                raise e
        else:
            logger.info('Waiting for {} s for run to finish'.format(self._run_time))
            self._stop_handle = self.service._connection.add_timeout(self._run_time, self.end_run)


    # checks whether psyllid run has stopped
    # if it hasn't, stops run
    # unblocks roach channel no matter what
    def _stop_data_taking(self):
        try:
            if self.is_running:
                logger.info('Psyllid still running. Telling it to stop the run')
                self.provider.cmd(self.psyllid_interface, 'stop_run', payload = self.payload_channel)
        except core.exceptions.DriplineError as e:
            logger.critical('Getting Psyllid status or stopping run failed')
            logger.info('Unblock channel')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
            finally:
                raise e
        except Exception as e:
            logger.critical('Something else went wrong')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
            finally:
                raise e
        else:
            logger.info('Unblock channel')
            payload = {'channel': self.channel_id}
            self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
            if self.status_value==None:
                raise core.exceptions.DriplineGenericDAQError('Psyllid must have crashed during run')


    # makes psyllid exit and unblocks roach channel
    def stop_psyllid(self):
        # in case things go really wrong...
        self.provider.cmd(self.psyllid_interface, 'quit_psyllid', payload = self.payload_channel)
        self.provider.cmd(self.daq_target, 'unblock_channel', payload = self.payload_channel)


    # frequency sets and gets
    def _get_roach_central_freqs(self):
        result = self.provider.get(self.daq_target + '.all_central_frequencies')
        logger.info('ROACH central freqs {}'.format(result))
        return result


    def _get_psyllid_central_freq(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_central_frequency', payload = self.payload_channel)
        logger.info('Psyllid central freqs {}'.format(result['values'][0]))
        return result['values'][0]


    @property
    def central_frequency(self):
        return self.freq_dict[self.channel_id]

    # sets central frequency in roach channel
    # roach2_interface returns true frequency (can deviate from requested cf)
    # sets same freqeuncy in psyllid instance
    # raises error if setting in psyllid failed (exceptions are caught in psyllid_provider)
    @central_frequency.setter
    def central_frequency(self, cf):
        payload = {'cf':float(cf), 'channel':self.channel_id}
        result = self.provider.cmd(self.daq_target, 'set_central_frequency', payload = payload)
        logger.info('The roach central frequency is now {}Hz'.format(result['values'][0]))

        # The roach frequency can differ from the requested frequency. Psyllid should have the same frequency settings as the ROACH
        self.freq_dict[self.channel_id]=round(result['values'][0])
        payload = {'channel':self.channel_id, 'cf':self.freq_dict[self.channel_id], 'channel':self.channel_id}
        self.provider.cmd(self.psyllid_interface, 'set_central_frequency', payload = payload)


    ### trigger control ###
    # all trigger parameters are properties here
    @property
    def snr_threshold(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_fmt_snr_threshold', payload = self.payload_channel)['values'][0]
        return result

    @snr_threshold.setter
    def snr_threshold(self, threshold):
        self.provider.cmd(self.psyllid_interface, 'set_fmt_snr_threshold', payload = {'channel': self.channel_id, 'threshold': threshold})
        self.provider.cmd(self.psyllid_interface, 'set_trigger_mode', payload = self.payload_channel)


    @property
    def snr_high_threshold(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_fmt_snr_high_threshold', payload = self.payload_channel)['values'][0]
        return result

    @snr_high_threshold.setter
    def snr_high_threshold(self, threshold):
        self.provider.cmd(self.psyllid_interface, 'set_fmt_snr_high_threshold', payload = {'channel': self.channel_id, 'threshold': threshold})
        self.provider.cmd(self.psyllid_interface, 'set_trigger_mode', payload = self.payload_channel)


    @property
    def n_triggers(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_n_triggers', payload = self.payload_channel)['values'][0]
        return result

    @n_triggers.setter
    def n_triggers(self, n_triggers):
        self.provider.cmd(self.psyllid_interface, 'set_n_triggers', payload = {'channel': self.channel_id, 'n_triggers': n_triggers})


    # changing the pretrigger time or the skip tolerance requires reactivation of psyllid
    # this results in the loss of all trigger settings
    @property
    def pretrigger_time(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_pretrigger_time', payload = self.payload_channel)['values'][0]
        return result

    @pretrigger_time.setter
    def pretrigger_time(self, pretrigger_time):
        self.provider.cmd(self.psyllid_interface, 'set_pretrigger_time', payload = {'channel': self.channel_id, 'pretrigger_time': pretrigger_time})
        self.provider.cmd(self.psyllid_interface, 'save_reactivate', payload = self.payload_channel)


    @property
    def skip_tolerance(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_skip_tolerance', payload = self.payload_channel)['values'][0]
        return result

    @skip_tolerance.setter
    def skip_tolerance(self, skip_tolerance):
        self.provider.cmd(self.psyllid_interface, 'set_skip_tolerance', payload = {'channel': self.channel_id, 'skip_tolerance': skip_tolerance})
        self.provider.cmd(self.psyllid_interface, 'save_reactivate', payload = self.payload_channel)


    # returns the type of trigger that is currently set
    @property
    def trigger_type(self):
        n_triggers = self.provider.cmd(self.psyllid_interface, 'get_n_triggers', payload = self.payload_channel)['values'][0]
        trigger_mode = self.provider.cmd(self.psyllid_interface, 'get_trigger_mode', payload = self.payload_channel)['values'][0]

        if n_triggers > 1:
            trigger_type = 'multi-trigger'
        else:
            trigger_type = trigger_mode

        return trigger_type

    @trigger_type.setter
    def trigger_type(self):
        raise core.exceptions.DriplineGenericDAQError('Trigger type is result of trigger settings and cannot be set directly')


    # returns all trigger settings
    @property
    def trigger_settings(self):
        if self.trigger_type == None:
            return False
        result = self.provider.cmd(self.psyllid_interface, 'get_trigger_configuration', payload = self.payload_channel)
        return result


    @trigger_settings.setter
    def trigger_settings(self, x):
        raise core.exceptions.DriplineGenericDAQError('Use configure_trigger command to set all trigger parameters at once')


    # set all trigger parameters with one command
    def configure_trigger(self, low_threshold, high_threshold, n_triggers):
        payload = {'threshold' : low_threshold, 'threshold_high' : high_threshold, 'n_triggers' : n_triggers, 'channel' : self.channel_id}
        self.provider.cmd(self.psyllid_interface, 'set_trigger_configuration', payload = payload)


    # returns pretrigger time and skip tolerance
    @property
    def time_window_settings(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_time_window', payload = self.payload_channel)
        return result

    @time_window_settings.setter
    def time_window_settings(self, x):
        raise core.exceptions.DriplineGenericDAQError('Use configure_time_window command to set skip_tolerance and pretrigger_time')


    # set pretrigger time and skip tolerance with one command
    def configure_time_window(self, pretrigger_time, skip_tolerance):
        payload =  {'skip_tolerance': skip_tolerance, 'pretrigger_time': pretrigger_time, 'channel' : self.channel_id}
        self.provider.cmd(self.psyllid_interface, 'set_time_window', payload = payload)


    # acquire and save new mask
    # raises exception if no mask_target_path was not set in config file
    def make_trigger_mask(self):
        if self.mask_target_path == None:
            logger.error('No target path set for trigger mask')
            raise core.exceptions.DriplineGenericDAQError('No target path set for trigger mask')

        timestr = time.strftime("%Y%m%d_%H%M%S")
        filename = '{}_frequency_mask_channel_{}_cf_{}.json'.format(timestr, self.channel_id, self.freq_dict[self.channel_id])
        path = os.path.join(self.mask_target_path, filename)
        payload = {'channel':self.channel_id, 'filename':path}
        self.provider.cmd(self.psyllid_interface, 'make_trigger_mask', payload = payload)

