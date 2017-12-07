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
                 mask_target = None,
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
        self.mask_target = mask_target
        self.payload_channel = {'channel':self.channel_id}

        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('The roach daq run interface interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq



    def _finish_configure(self):
        logger.info('Doing setup checks...')
        self._check_psyllid_instance()
        
        if self.status_value == 0:
            self.provider.cmd(self.psyllid_interface, 'activate', payload = self.payload_channel)
            self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)['values'][0]
                
        if self._check_roach2_is_ready()==False:
            logger.warning('ROACH2 check indicates ADC is not calibrated')

        logger.info('Setting Psyllid central frequency identical to ROACH2 central frequency')
        freqs = self._get_roach_central_freqs()
        self.central_frequency = freqs[self.channel_id]


    @property
    def is_running(self):
        result = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel, timeout=10)
        self.status_value = result['values'][0]
        logger.info('psyllid status is {}'.format(self.status_value))
        if self.status_value==5:
            return True
        else:
            return False

    @property
    def max_duration(self):
        return self._max_duration

    @max_duration.setter
    def max_duration(self, duration):
        self._max_duration = duration


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


    def _check_psyllid_instance(self):
        logger.info('Checking Psyllid service & instance')

        #check psyllid is responding by requesting status
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)['values'][0]
        if self.status_value == None:
            logger.error('Psyllid is not responding')
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not responding')        

        #check channel match
        active_channels = self.provider.get(self.psyllid_interface + '.active_channels')
        logger.info(active_channels)
        if self.channel_id in active_channels==False:
            logger.error('The Psyllid and ROACH2 channel interfaces do not match')
            raise core.exceptions.DriplineGenericDAQError('The Psyllid and ROACH channel interfaces do not match')


    def _do_checks(self):
        if self._run_time ==0:
            raise core.exceptions.DriplineValueError('run time is zero')

        #checking psyllid
        if self.is_running==True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is already running')

        self._check_psyllid_instance()

        if self.status_value!=4:
            raise core.exceptions.DriplineGenericDAQError('Psyllid DAQ is not activated')

        #checking roach
        if self._check_roach2_is_ready() == False:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not ready. ADC not calibrated.')
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



    def _start_data_taking(self, directory, filename):
        logger.info('block roach channel')
        self.provider.cmd(self.daq_target, 'block_channel', payload=self.payload_channel)
        logger.info('start data taking')

        # switching from seconds to milisecons
        duration = self._run_time*1000.0
        logger.info('run duration in ms: {}'.format(duration))

        psyllid_filename = filename+'.egg'
        if not os.path.exists(directory):
            os.makedirs(directory)

        logger.info('Going to tell psyllid to start the run')
        payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':duration}
        try:
            self.provider.cmd(self.psyllid_interface, 'start_run', payload=payload)
        except core.exceptions.DriplineError:
            logger.error('Error from psyllid provider or psyllid')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
            finally:
                raise core.exceptions.DriplineGenericDAQError('Starting psyllid run failed')
        except Exception as e:
            logger.error('Local error')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload=payload)
            finally:
                raise e
        else:
            logger.info('waiting for {}s for run to finish'.format(self._run_time))
            self._stop_handle = self.service._connection.add_timeout(self._run_time, self.end_run)



    def _stop_data_taking(self):
        try:
            if self.is_running:
                logger.info('Psyllid still running. Telling it to stop the run')
                self.provider.cmd(self.psyllid_interface, 'stop_run', payload = self.payload_channel)
        except core.exceptions.DriplineError:
            logger.error('Getting Psyllid status at end of run failed')
            logger.info('unblock channel')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload=payload)
            finally:
                raise core.exceptions.DriplineGenericDAQError('Error at end of run')
        except Exception as e:
            logger.error('Local error at end of run')
            logger.info('unblock channel')
            payload = {'channel': self.channel_id}
            try:
                self.provider.cmd(self.daq_target, 'unblock_channel', payload=payload)
            finally:
                raise e
        else:
            payload = {'channel': self.channel_id}
            self.provider.cmd(self.daq_target, 'unblock_channel', payload=payload)
            if self.status_value==None:
                raise core.exceptions.DriplineGenericDAQError('Psyllid must have crashed during run')


    def adopt_new_psyllid_instance(self):
        self.provider.cmd(self.psyllid_interface, 'get_acquisition_mode', payload = self.payload_channel)
        self._finish_configure()


    def stop_psyllid(self):
        # in case things go really wrong...
        self.provider.cmd(self.psyllid_interface, 'quit_psyllid', payload = self.payload_channel)
        self.provider.cmd(self.daq_target, 'unblock_channel', payload=self.payload_channel)


# frequency settings and gettings

    def _get_roach_central_freqs(self):
        result = self.provider.get(self.daq_target + '.all_central_frequencies')
        logger.info('ROACH central freqs {}'.format(result))
        return result


    def _get_psyllid_central_freq(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_central_frequency', payload=self.payload_channel)
        logger.info('Psyllid central freqs {}'.format(result['values'][0]))
        return result['values'][0]


    @property
    def central_frequency(self):
        return self.freq_dict[self.channel_id]


    @central_frequency.setter
    def central_frequency(self, cf):
        payload={'cf':float(cf), 'channel':self.channel_id}
        result = self.provider.cmd(self.daq_target, 'set_central_frequency', payload=payload)
        logger.info('The roach central frequency is now {}Hz'.format(result['values'][0]))
        # The roach frequency can differ from the requested frequency. Psyllid should have the same frequency settings as the ROACH
        self.freq_dict[self.channel_id]=round(result['values'][0])
        payload={'channel':self.channel_id, 'cf':self.freq_dict[self.channel_id], 'channel':self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_central_frequency', payload=payload)
        if result['values'][0]!=True:
            logger.warning('Could not set central frequency in Psyllid')
            self.freq_dict[self.channel_id]=None
            raise core.exceptions.DriplineGenericDAQError('Could not set central frequency in Psyllid stream')

    @property
    def trigger_type(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_trigger_configuration', payload=self.payload_channel)
        logger.info(result)

        if result['threshold'] == False:
            trigger_type = 'untriggered'
        if result['n_triggers'] >1:
            trigger_type = 'multi_trigger'
        elif result['threshold_high'] != None:
            trigger_type = 'two_thresholds'
        else:
            trigger_type = 'single_threshold'

        return trigger_type


    @property
    def single_threshold_trigger(self):
        logger.info(self.trigger_type)
        if self.trigger_type != 'single_threshold':
            return False
        threshold = self.provider.cmd(self.psyllid_interface, 'get_trigger_configuration', payload=self.payload_channel)['threshold']
        return {'threshold' : threshold}

    def set_single_threshold_trigger(self, threshold):
        payload = {'threshold' : threshold, 'threshold_high' : 0.0, 'n_triggers' : 1, 'channel' : self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_trigger_configuration', payload=payload)
        logger.info(result)
        if result == False:
            logger.error('Could not apply trigger settings')
            raise core.exceptions.DriplineGenericDAQError('Could not apply trigger settings. Psyllid instance not in triggered mode')


    @property
    def two_threshold_trigger(self):
        if self.trigger_type != 'two_thresholds':
            return False
        result = self.provider.cmd(self.psyllid_interface, 'get_trigger_configuration', payload=self.payload_channel)
        return {'low_threshold': result['threshold'], 'high_threshold' : result['threshold_high']}

    def set_two_threshold_trigger(self, high_threshold, low_threshold):
        payload = {'threshold' : low_threshold, 'threshold_high' : high_threshold, 'n_triggers' : 1, 'channel' : self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_trigger_configuration', payload=payload)
        logger.info(result)
        if result== False:
            logger.error('Could not apply trigger settings')
            raise core.exceptions.DriplineGenericDAQError('Could not apply trigger settings. Psyllid instance not in triggered mode')


    @property
    def multi_trigger(self):
        if self.trigger_type != 'multi_trigger':
            return False
        result = self.provider.cmd(self.psyllid_interface, 'get_trigger_configuration', payload=self.payload_channel)
        skip_tolerance = self.provider.cmd(self.psyllid_interface, 'get_time_window', payload=self.payload_channel)['skip_tolerance']
        return {'threshold' : result['threshold'], 'n_triggers' : result['n_triggers'], 'skip_tolerance': skip_tolerance}

    def set_multi_trigger(self, threshold, n_triggers):
        payload = {'threshold' : threshold, 'threshold_high' : 0.0, 'n_triggers' : n_triggers, 'channel' : self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_trigger_configuration', payload=payload)
        logger.info(result)
        if result== False:
            logger.error('Could not apply trigger settings')
            raise core.exceptions.DriplineGenericDAQError('Could not apply trigger settings. Psyllid instance not in triggered mode')


    @property
    def time_window(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_time_window', payload=self.payload_channel)
        return {'skip_tolerance': result['skip_tolerance'], 'pretrigger_time': result['pretrigger_time']}

    def set_time_window(self, pretrigger_time, skip_tolerance):
        payload =  {'skip_tolerance': skip_tolerance, 'pretrigger_time': pretrigger_time, 'channel' : self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_time_window', payload=payload)
        logger.info(result)
        if result == False:
            logger.error('Could not time window trigger settings')
            raise core.exceptions.DriplineGenericDAQError('Could not timw window settings. Psyllid instance not in triggered mode')


    def make_trigger_mask(self):
        # Set threshold snr
        payload = {'channel':self.channel_id}
        # Acquire and save new mask
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = '{}_frequency_mask_channel_{}_cf_{}.json'.format(timestr, self.channel_id, self.freq_dict[self.channel_id])
        path = os.path.join(self.mask_target, filename)
        payload = {'channel':self.channel_id, 'filename':path}
        result = self.provider.cmd(self.psyllid_interface, 'make_trigger_mask', payload=payload)
        if result['values'][0]!=True:
            return False
        else: return True
