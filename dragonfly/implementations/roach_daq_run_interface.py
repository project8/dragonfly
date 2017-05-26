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
                 psyllid_interface='psyllid_interface',
                 daq_target = 'roach2_interface',
                 channel = 'a',
                 hf_lo_freq = None,
                 **kwargs
                ):

        DAQProvider.__init__(self, **kwargs)

        self.psyllid_interface = psyllid_interface
        self.daq_target = daq_target
        self.status_value = None
        self.channel_id = channel
        self.freq_dict = {self.channel_id: None}
        self._max_duration = 0
        self._run_time = 1
        self._run_name = "test"
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
                
        if self._check_roach2_is_ready()==True:
            logger.info('Setting Psyllid central frequency identical to ROACH2 central frequency')
            freqs = self._get_roach_central_freqs()
            self.central_frequency = freqs[self.channel_id]
        else:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not ready for data taking')


    @property
    def is_running(self):
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)
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
            logger.info('ROACH2 is ready')
            return True
        else:
            logger.info('ROACH2 is not ready')
            return False


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
        #elif self._run_time >= self._max_duration:
        #    raise core.exceptions.DriplineValueError('run time exceeds max duration')

        #checking psyllid
        if self.is_running==True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is already running')

        self._check_psyllid_instance()

        if self.status_value!=4:
            raise core.exceptions.DriplineGenericDAQError('Psyllid DAQ is not activated')

        #checking roach
        if self._check_roach2_is_ready() == False:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not ready')
        blocked_channels = self.provider.get(self.daq_target+ '.blocked_channels')
        logger.info(blocked_channels)
        if self.channel_id in blocked_channels: 
            raise core.exceptions.DriplineGenericDAQError('Channel is blocked')

        #check frequency matches
        roach_freqs = self._get_roach_central_freqs()
        psyllid_freq = self._get_psyllid_central_freq()
        if roach_freqs[self.channel_id]!=psyllid_freq:
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
        max_duration = self._max_duration*1000.0
        logger.info('run duration in ms: {}'.format(duration))

        if self._max_duration == 0.0:
            logger.info('no max duration set in dragonfly')
            NAcquisitions = 1
        else:
            NAcquisitions = duration/max_duration

        if NAcquisitions<=1:
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

        # if the run time exceeds the set max duration the run is split into sub acquisitions
        # this will be removed once we are sure psyllid can handle it even for long runs
        else:
            logger.info('Doing {} acquisitions'.format(int(NAcquisitions)))
            for i in range(int(NAcquisitions)):
                total_run_time = 0.0
                psyllid_filename = filename+'_'+str(i)+'.egg'
                logger.info('Data will be written to {}/{}'.format(directory, psyllid_filename))
                if not os.path.exists(directory):
                    os.makedirs(directory)

                # last acquisition
                if total_run_time > duration-max_duration:
                    duration = duration-total_run_time
                    logger.info('Going to tell psyllid to start the last run')
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

                # acquisitions with duration = max_duration
                else:
                    total_run_time+=max_duration
                    logger.info('Going to tell psyllid to start run')
                    payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':max_duration}

                    try:
                        self.provider.cmd(self.psyllid_interface, 'start_run', payload=payload)
                        time.sleep(self._max_duration)
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



    def _stop_data_taking(self):
        if self.is_running:
            self.provider.cmd(self.psyllid_interface, 'stop_run', payload = self.payload_channel)
        logger.info('unblock channel')
        payload = {'channel': self.channel_id}
        result = self.provider.cmd(self.daq_target, 'unblock_channel', payload=payload)


    def adopt_new_psyllid_instance(self):
        self._finish_configure()


    def stop_psyllid(self):
        # in case things go really wrong...
        self.provider.cmd(self.psyllid_interface, 'quit_psyllid', payload = self.payload_channel)
        self.provider.cmd(self.daq_target, 'unblock_channel', payload=self.payload_channel)

#    def _set_condition(self, number):
#        if number in self._set_condition_list:
#            logger.debug('deactivate psyllid daq')
#            result = self.provider.cmd(self.psyllid_interface, 'activate', payload = self.payload_channel)
#        elif number == 0:
#            logger.debug('getting out of safe mode')
#        else:
#            logger.debug('condition {} is unknown: ignoring!'.format(number))


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
        payload={'cf':cf, 'channel':self.channel_id}
        result = self.provider.cmd(self.daq_target, 'set_central_frequency', payload=payload)
        # The roach frequency can differ from the requested frequency. Psyllid should have the same frequency settings as the ROACH
        self.freq_dict[self.channel_id]=result['values'][0]
        payload={'channel':self.channel_id, 'cf':self.freq_dict[self.channel_id], 'channel':self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_central_frequency', payload=payload)
        if result['values'][0]!=True:
            logger.warning('Could not set central frequency in Psyllid')
            self.freq_dict[self.channel_id]=None
            raise core.exceptions.DriplineGenericDAQError('Could not set central frequency in Psyllid stream')


    def make_trigger_mask(self, snr, filename = '/home/roach/trigger_masks/psyllid_trigger_mask'):
        # Set threshold snr
        payload = {'channel':self.channel_id, 'snr':snr}
        self.provider.cmd(self.psyllid_interface, 'set_fmt_snr_threshold', payload = payload)
        time.sleep(1)
        # Acquire and save new mask
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = '{}_channel_{}_{}.json'.format(filename, self.channel_id, timestr)
        payload = {'channel':self.channel_id, 'filename':filename}
        result = self.provider.cmd(self.psyllid_interface, 'make_trigger_mask', payload=payload)
        if result['values'][0]!=True:
            return False
        else: return True
