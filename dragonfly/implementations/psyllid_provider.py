'''
'''

from __future__ import absolute_import

# standard imports
import logging
import time

# internal imports
from dripline import core


__all__ = []

logger = logging.getLogger(__name__)


__all__.append('PsyllidProvider')
class PsyllidProvider(core.Provider):
    '''
    Provider for direct communication with up to 3 Psyllid instances with a single stream each
    '''
    def __init__(self,
                 set_condition_list = [],
                 channel_dict = {'a': 'ch0', 'b': 'ch1', 'c': 'ch2'},
                 queue_dict = {'a': 'channel_a_psyllid', 'b': 'channel_b_psyllid', 'c': 'channel_c_psyllid'},
                 temp_file = '/tmp/empty_egg_file.egg',
                 **kwargs):

        core.Provider.__init__(self, **kwargs)
        self._set_condition_list = set_condition_list
        self.queue_dict = queue_dict
        self.channel_dict = channel_dict
        self.freq_dict = {x: None for x in channel_dict.keys()}
        self.mode_dict = {x: None for x in channel_dict.keys()}
        self.status_dict = {x: None for x in channel_dict.keys()}
        self.status_value_dict = {x: None for x in channel_dict.keys()}
        self.temp_file = temp_file


    def check_all_psyllid_instances(self):
        '''
        Populates all dictionaries by checking the configuarions of all psyllid instances
        '''
        for channel in self.channel_dict.keys():
            try:
                self.request_status(channel)
                self.get_acquisition_mode(channel)
                if self.freq_dict[channel] == None:
                    self.freq_dict[channel] = 50.0e6
                self.set_central_frequency(channel, self.freq_dict[channel])
            except core.exceptions.DriplineError:
                self.status_dict[channel] = None
                self.status_value_dict[channel] = None
                self.mode_dict[channel] = None
                self.freq_dict[channel] = None

        # Summary
        logger.info('Status of channels: {}'.format(self.status_value_dict))
        logger.info('Set central frequencies: {}'.format(self.freq_dict))
        logger.info('Streaming or triggering mode: {}'.format(self.mode_dict))


    @property
    def all_acquisition_modes(self):
        '''
        Returns mode_dict containing the information which psyllid instance is in triggering or streaming mode
        Stopped psyllid instances are in acquisition mode None
        Content of mode_dict is not updated at this point
        Content of mode_dict is updated by calling prepare_daq_system (in roach_daq_run_interface) or check_all_psyllid_instances
        '''
        return self.mode_dict


    @all_acquisition_modes.setter
    def all_acquisition_modes(self, x):
        raise core.exceptions.DriplineGenericDAQError('acquisition_modes cannot be set')


    @property
    def active_channels(self):
        '''
        Returns the number of psyllid instances that are activated
        '''
        active_channels = [i for i in self.status_value_dict.keys() if self.status_value_dict[i]==4]
        return active_channels


    @active_channels.setter
    def active_channels(self, x):
        raise core.exceptions.DriplineGenericDAQError('active_channels cannot be set')


    def get_active_config(self, channel, key):
        target = '{}.active-config.{}.{}'.format(self.queue_dict[channel],
                                                 str(self.channel_dict[channel]),
                                                 key)
        self.provider.get(target)


    def get_acquisition_mode(self, channel):
        '''
        Tests whether psyllid is in streaming or triggering mode
        '''
        try:
            self.mode_dict[channel] = 'triggering'
            self.get_central_frequency(channel)
        except core.exceptions.DriplineError:
            self.mode_dict[channel] = 'streaming'
            try:
                self.get_central_frequency(channel)
            except core.exceptions.DriplineError as e:
                self.mode_dict[channel] = None
                raise e
        return {'mode': self.mode_dict[channel]}


    def get_number_of_streams(self, channel):
        '''
        Counts how many streams (streaming or triggering) are set up in psyllid and retuns number
        '''
        stream_count = 0
        for i in range(3):
            try:
                request = '.node-config.ch'+str(i)+'.strw'
                self.provider.get(self.queue_dict[channel]+request)
                stream_count += 1
                self.mode_dict[channel]='streaming'
            except core.exceptions.DriplineError:
                try:
                    request = '.node-config.ch'+str(i)+'.trw'
                    self.provider.get(self.queue_dict[channel]+request)
                    stream_count += 1
                    self.mode_dict[channel]='triggering'
                except core.exceptions.DriplineError:
                    pass
        logger.info('Number of streams for channel {}: {}'.format(channel, stream_count))
        return stream_count


    def request_status(self, channel):
        '''
        Asks the psyllid instance what state it is in and returns that state
        '''
        logger.info('Checking Psyllid status of channel {}'.format(channel))
        result = self.provider.get(self.queue_dict[channel]+'.daq-status', timeout=5)
        self.status_dict[channel] = result['server']['status']
        self.status_value_dict[channel] = result['server']['status-value']
        logger.info('Psyllid is running. Status is {}'.format(self.status_dict[channel]))
        logger.info('Status in numbers: {}'.format(self.status_value_dict[channel]))
        return self.status_value_dict[channel]


    def activate(self, channel):
        '''
        Tells psyllid to activate and checks whether activation was successful
        '''
        if self.status_value_dict[channel] == 0:
            logger.info('Activating Psyllid instance for channel {}'.format(channel))
            self.provider.cmd(self.queue_dict[channel], 'activate-daq')
        else:
            logger.error('Cannot activate Psyllid instance of channel {}'.format(channel))
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not deactivated')
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=4:
            logger.error('Activating failed')
            raise core.exceptions.DriplineGenericDAQError('Activating psyllid failed')


    def deactivate(self, channel):
        '''
        Tells psyllid to deactivate and checks whether deactivation was successful
        '''
        if self.status_value_dict[channel] != 0:
            logger.info('Deactivating Psyllid instance of channel {}'.format(channel))
            self.provider.cmd(self.queue_dict[channel],'deactivate-daq')
        else:
            logger.error('Cannot deactivate Psyllid instance of channel {}'.format(channel))
            raise core.exceptions.DriplineGenericDAQError('Psyllid is already deactivated')
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=0:
            logger.error('Deactivating failed')
            raise core.exceptions.DriplineGenericDAQError('Deactivating psyllid failed')


    def reactivate(self, channel):
        '''
        Tells psyllid to reactivate and checks whether reactivation was successful
        '''
        if self.status_value_dict[channel] == 4:
            logger.info('Reactivating Psyllid instance of channel {}'.format(channel))
            self.provider.cmd(self.queue_dict[channel], 'reactivate-daq')
        else:
            logger.error('Cannot reactivate Psyllid instance of channel {}'.format(channel))
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not activated and can therefore not be reactivated')
        time.sleep(2)
        self.request_status(channel)
        if self.status_value_dict[channel]!=4:
            logger.error('Reactivating failed')
            raise core.exceptions.DriplineGenericDAQError('Reactivating psyllid failed')


    def save_reactivate(self, channel):
        '''
        Reactivate results in the loss of all active-node configurations
        This method stores settings and re-sets them after reactivation
        '''
        if self.mode_dict[channel] == 'triggering':
            # store trigger configuration
            result = self.get_trigger_configuration(channel)
        # reactivate psyllid (all trigger and frequency settings are lost)
        self.reactivate(channel)
        # re-set central frequency
        self.set_central_frequency(channel, self.freq_dict[channel])
        if self.mode_dict[channel] == 'triggering':
            # re-set trigger configuration
            self.set_trigger_configuration(channel=channel, threshold=result['threshold'], threshold_high=result['threshold_high'], n_triggers=result['n_triggers'])


    def quit_psyllid(self, channel):
        '''
        Tells psyllid to quit
        '''
        self.provider.cmd(self.queue_dict[channel], 'quit-psyllid')
        logger.info('psyllid quit!')


    @property
    def all_central_frequencies(self):
        '''
        Returns a dictionary with all central frequencies
        '''
        return self.freq_dict


    @all_central_frequencies.setter
    def all_central_frequencies(self, x):
        raise core.exceptions.DriplineGenericDAQError('all_central_frequencies cannot be set')


    def get_central_frequency(self, channel):
        '''
        Gets central frequency from psyllid and returns it
        '''
        if self.mode_dict[channel] == None:
            logger.error('Acquisition mode is None. Cannot get central frequency from psyllid')
            raise core.exceptions.DriplineGenericDAQError('Acquisition mode is None. Update mode by using get_acquisition_mode command')
        routing_key_map = {
                           'streaming':'strw',
                           'triggering':'trw'
                          }
        request = 'active-config.{}.{}'.format(self.channel_dict[channel], routing_key_map[self.mode_dict[channel]])
        result = self.provider.get(self.queue_dict[channel]+'.'+request)
        logger.info('Psyllid says cf is {}'.format(result['center-freq']))
        self.freq_dict[channel]=result['center-freq']
        return self.freq_dict[channel]


    def set_central_frequency(self, channel, cf):
        '''
        Sets central frequency in psyllid
        '''
        if self.mode_dict[channel] == None:
            logger.error('Acquisition mode is None. Cannot set central frequency from psyllid')
            raise core.exceptions.DriplineGenericDAQError('Acquisition mode is None. Update mode by using get_acquisition_mode command')
        routing_key_map = {
                           'streaming':'strw',
                           'triggering':'trw'
                          }
        request = '.active-config.{}.{}.center-freq'.format(self.channel_dict[channel], routing_key_map[self.mode_dict[channel]])
        self.provider.set(self.queue_dict[channel]+request, cf)
        logger.info('Set central frequency of {} writer for channel {} to {} Hz'.format(self.mode_dict[channel], channel, cf))
        self.freq_dict[channel]=cf


    def is_psyllid_using_monarch(self, channel):
        '''
        Check psyllid is using monarch
        If it isn't psyllid cannot write files and runs will fail
        '''
        result =  self.provider.get(self.queue_dict[channel]+'.use-monarch')['values'][0]
        logger.info('Psyllid channel {} is using monarch: {}'.format(channel, result))
        return result


    def start_run(self, channel, duration, filename):
        '''
        Tells psyllid to start a run
        Payload is run duration and egg-filename
        '''
        payload = {'duration':duration, 'filename':filename}
        self.provider.cmd(self.queue_dict[channel], 'start-run', payload=payload)


    def stop_run(self, channel):
        '''
        Tells psyllid to stop a run
        This method is for interrupting runs
        Runs stop automatically after the set duration and normally don't need to be stopped manually
        '''
        self.provider.cmd(self.queue_dict[channel], 'stop-run')


    ###################
    # trigger control #
    ###################

    def set_trigger_configuration(self, channel='a', threshold=18, threshold_high=0, n_triggers=1,):
        '''
        Set all trigger parameters at once
        '''
        self.set_fmt_snr_threshold( threshold, channel )
        self.set_fmt_snr_high_threshold( threshold_high, channel )
        self.set_n_triggers( n_triggers, channel )
        self.set_trigger_mode( channel )


    def get_trigger_configuration(self, channel='a'):
        '''
        Gets and returns all trigger parameters
        '''
        threshold = self.get_fmt_snr_threshold( channel )
        threshold_high = self.get_fmt_snr_high_threshold( channel )
        n_triggers = self.get_n_triggers( channel )
        trigger_mode = self.get_trigger_mode( channel )

        return {'threshold': threshold, 'threshold_high' : threshold_high, 'n_triggers' : n_triggers, 'trigger_mode' : trigger_mode}


    def set_time_window(self, channel='a', pretrigger_time=2e-3, skip_tolerance=5e-3):
        '''
        Does all time window settings at once
        '''
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError('Psyllid instance is not in triggering mode')
        # apply settings
        self.set_pretrigger_time( pretrigger_time, channel )
        self.set_skip_tolerance( skip_tolerance, channel )
        # reactivate without loosing active-node settings
        self.save_reactivate( channel )


    def get_time_window(self, channel='a'):
        '''
        Gets and returns all time window settings
        '''
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError('Psyllid instance is not in triggering mode')

        pretrigger_time = self.get_pretrigger_time( channel )
        skip_tolerance = self.get_skip_tolerance( channel )

        return {'pretrigger_time': pretrigger_time, 'skip_tolerance': skip_tolerance}


    ##############################################################
    # individual time window and trigger parameter sets and gets #
    ##############################################################

    def set_pretrigger_time(self, pretrigger_time, channel='a'):
        n_pretrigger_packets = int(round(pretrigger_time/4.096e-5))
        logger.info('Setting psyllid pretrigger to {} packets'.format(n_pretrigger_packets))
        request = '.node-config.{}.eb.pretrigger'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, n_pretrigger_packets)


    def get_pretrigger_time(self, channel='a'):
        request = '.active-config.{}.eb.pretrigger'.format(str(self.channel_dict[channel]))
        n_pretrigger_packets = self.provider.get(self.queue_dict[channel]+request)['pretrigger']
        return float(n_pretrigger_packets) * 4.096e-5


    def set_skip_tolerance(self, skip_tolerance, channel='a'):
        n_skipped_packets = int(round(skip_tolerance/4.096e-5))
        logger.info('Setting psyllid skip tolerance to {} packets'.format(n_skipped_packets))
        request = '.node-config.{}.eb.skip-tolerance'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, n_skipped_packets)


    def get_skip_tolerance(self, channel='a'):
        request = '.active-config.{}.eb.skip-tolerance'.format(str(self.channel_dict[channel]))
        n_skipped_packets = self.provider.get(self.queue_dict[channel]+request)['skip-tolerance']
        return float(n_skipped_packets) * 4.096e-5


    def set_fmt_snr_threshold(self, threshold, channel='a'):
        request = '.active-config.{}.fmt.threshold-power-snr'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, threshold)
        logger.info('Setting psyllid power snr threshold to {}'.format(threshold))


    def get_fmt_snr_threshold(self, channel='a'):
        request = '.active-config.{}.fmt.threshold-power-snr'.format(str(self.channel_dict[channel]))
        threshold = self.provider.get(self.queue_dict[channel]+request)['threshold-power-snr']
        return float(threshold)


    def set_fmt_snr_high_threshold(self, threshold, channel='a'):
        request = '.active-config.{}.fmt.threshold-power-snr-high'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, threshold)
        logger.info('Setting psyllid power snr threshold to {}'.format(threshold))


    def get_fmt_snr_high_threshold(self, channel='a'):
        request = '.active-config.{}.fmt.threshold-power-snr-high'.format(str(self.channel_dict[channel]))
        threshold = self.provider.get(self.queue_dict[channel]+request)['threshold-power-snr-high']
        return float(threshold)


    def _set_trigger_mode(self, mode_id, channel='a'):
        request = '.active-config.{}.fmt.trigger-mode'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, mode_id)
        logger.info('Setting psyllid trigger mode to {}'.format(mode_id))


    def set_trigger_mode(self, channel='a'):
        if self.get_fmt_snr_high_threshold(channel) > self.get_fmt_snr_threshold(channel):
            self._set_trigger_mode('two-level-trigger', channel)
        else:
            self._set_trigger_mode('single-level-trigger', channel)


    def get_trigger_mode(self, channel='a'):
        request = '.active-config.{}.fmt.trigger-mode'.format(str(self.channel_dict[channel]))
        trigger_mode = self.provider.get(self.queue_dict[channel]+request)['trigger-mode']
        return trigger_mode


    def set_n_triggers(self, n_triggers, channel='a'):
        request = '.active-config.{}.eb.n-triggers'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, n_triggers)
        logger.info('Setting psyllid n-trigger/skip-tolerance to {}'.format(n_triggers))


    def get_n_triggers(self, channel='a'):
        request = '.active-config.{}.eb.n-triggers'.format(str(self.channel_dict[channel]))
        n_triggers = self.provider.get(self.queue_dict[channel]+request)['n-triggers']
        return n_triggers


    def make_trigger_mask(self, channel='a', filename='~/fmt_mask.json'):
        '''
        Tells psyllid to record a frequency mask, write it to a json file and prepare for triggering run
        '''
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError('Psyllid instance is not in triggering mode')

        logger.info('Switch tf_roach_receiver to freq-only')
        request = 'run-daq-cmd.{}.tfrr.freq-only'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)

        logger.info('Switch frequency_mask_trigger to update-mask')
        request = 'run-daq-cmd.{}.fmt.update-mask'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)
        time.sleep(1)

        logger.info('Telling psyllid to not use monarch when starting next run')
        self.provider.set(self.queue_dict[channel]+'.use-monarch', False)

        logger.info('Start short run to record mask')
        self.start_run(channel ,1000, self.temp_file)
        time.sleep(1)

        self._write_trigger_mask(channel, filename)

        logger.info('Telling psyllid to use monarch again for next run')
        self.provider.set(self.queue_dict[channel]+'.use-monarch', True)

        logger.info('Switch tf_roach_receiver back to time and freq')
        request = 'run-daq-cmd.{}.tfrr.time-and-freq'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)

        logger.info('Switch frequency mask trigger to apply-trigger')
        request = 'run-daq-cmd.{}.fmt.apply-trigger'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)


    def _write_trigger_mask(self, channel, filename):
        '''
        Tells psyllid to write a frequency mask to a json file
        '''
        logger.info('Write mask to file')
        request = 'run-daq-cmd.{}.fmt.write-mask'.format(str(self.channel_dict[channel]))
        payload = {'filename': filename}
        self.provider.cmd(self.queue_dict[channel], request, payload=payload)
