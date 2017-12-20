'''
'''

from __future__ import absolute_import

# standard imports
import logging
import time
from datetime import datetime

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
                 queue_a='channel_a_psyllid',
                 queue_b = 'channel_b_psyllid',
                 queue_c = 'channel_c_psyllid',
                 set_condition_list = [],
                 channel_dict = {'a': 'ch0', 'b': 'ch1', 'c': 'ch2'},
                 temp_file = '/temp/empty_egg_file.egg',
                 **kwargs):

        core.Provider.__init__(self, **kwargs)        
        self.queue_dict = {'a':queue_a, 'b':queue_b, 'c':queue_c}
        self._set_condition_list = set_condition_list
        self.channel_dict = channel_dict
        self.freq_dict = {x: None for x in channel_dict.keys()}
        self.mode_dict = {x: None for x in channel_dict.keys()}
        self.status_dict = {x: None for x in channel_dict.keys()}
        self.status_value_dict = {x: None for x in channel_dict.keys()}
        self.mode_testing = False
        self.temp_file = temp_file


    # check_all_psyllid_instances populates all dictionaries by checking te configuarions of all psyllid instances
    def check_all_psyllid_instances(self):
        for channel in self.channel_dict.keys():
            if self.request_status(channel)!=None:
                try:
                    self.get_acquisition_mode(channel)
                    if self.mode_dict[channel]==None:
                        raise core.exceptions.DriplineGenericDAQError("Stream writer of Psyllid instance for channel {} is not configured correctly".format(channel))

                    if self.get_number_of_streams(channel)!=1:
                        self.mode_dict[channel]=None
                        raise core.exceptions.DriplineGenericDAQError("Streams of Psyllid instance for channel {} are not configured correctly".format(channel))

                except core.exceptions.DriplineGenericDAQError:
                    logger.warning('No matching Psyllid instance for channel {} present'.format(channel))


        # Summary after startup
        logger.info('Status of channels: {}'.format(self.status_value_dict))
        logger.info('Set central frequencies: {}'.format(self.freq_dict))
        logger.info('Streaming or triggering mode: {}'.format(self.mode_dict))


    # returns mode_dict which contains the information which psyllid instance is in triggering or streaming mode
    # stopped psyllid instances are in acquisition mode None
    # content of mode_dict is not verified by (re-) checking psyllid
    # content of mode_dict is updated by calling prepare_daq_system (in roach_daq_run_interface) or check_all_psyllid_instances
    @property
    def acquisition_modes(self):
        return self.mode_dict


    # returns the number of psyllid instances that are in activated
    @property
    def active_channels(self):
        active_channels = [i for i in self.status_value_dict.keys() if self.status_value_dict[i]==4]
        return active_channels


    # tests whether psyllid is in streaming or triggering mode
    def get_acquisition_mode(self, channel):
        self.mode_testing = True
        if self.freq_dict[channel]!=None:
            cf = self.freq_dict[channel]
        else:
            cf = 800e6
        self.mode_dict[channel]='streaming'
        if self.set_central_frequency(channel=channel, cf=cf)==False:
           logger.info('Psyllid is not in streaming mode')
           self.mode_dict[channel]='triggering'
           if self.set_central_frequency(channel=channel, cf=cf)==False:
                self.mode_dict[channel]=None
                logger.info('Psyllid is not in triggering mode')
        self.mode_testing = False
        return self.mode_dict[channel]


    # counts how many streams (stremaing or triggering) are set up in psyllid and retuns number 
    def get_number_of_streams(self, channel):
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


    # asks the psyllid instance what state it is in and returns that state
    # if no psyllid is running exception is caught and status set to None
    def request_status(self, channel):
        logger.info('Checking Psyllid status of channel {}'.format(channel))
        try:
            result = self.provider.get(self.queue_dict[channel]+'.daq-status', timeout=5)
        except core.exceptions.DriplineError:
            logger.info('Psyllid instance for channel {} is not running or returned error'.format(channel))
            self.status_dict[channel]=None
            self.status_value_dict[channel]=None
            return self.status_value_dict[channel]
        except Exception as e:
            logger.error('Something else went wrong')
            raise e
        else:
            self.status_dict[channel] = result['server']['status']
            self.status_value_dict[channel] = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status_dict[channel]))
            logger.info('Status in numbers: {}'.format(self.status_value_dict[channel]))
            return self.status_value_dict[channel]


    # tells psyllid to activate and checks whether activation was successful
    def activate(self, channel):
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


    # tells psyllid to deactivate and checks whether deactivation was successful
    def deactivate(self, channel):
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


    # tells psyllid to reactivate and checks whether reactivation was successful
    def reactivate(self, channel):
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


    # tells psyllid to quit
    def quit_psyllid(self, channel):
        self.provider.cmd(self.queue_dict[channel], 'quit-psyllid')
        logger.info('psyllid quit!')


    # returns a dictionary with all central frequencies
    @property
    def all_central_frequencies(self):
        return self.freq_dict


    # asks psyllid what the set central frequency is and returns it
    def get_central_frequency(self, channel):
        routing_key_map = {
                           'streaming':'strw',
                           'triggering':'trw'
                          }
        request = 'active-config.{}.{}'.format(self.channel_dict[channel], routing_key_map[self.mode_dict[channel]])
        result = self.provider.get(self.queue_dict[channel]+'.'+request)
        logger.info('Psyllid says cf is {}'.format(result['center-freq']))
        self.freq_dict[channel]=result['center-freq']
        return self.freq_dict[channel]

    
    # sets central frequency in psyllid
    # returns True in case of success and Fals in case of failure because this method is used by get_acquisition mode which checks the return
    # if it is not used for testing the mode, failing to set the central frequency will result in error
    def set_central_frequency(self, channel, cf):
        #logger.info('Trying to set cf of channel {} to {}'.format(channel, cf))
        routing_key_map = {
                           'streaming':'strw',
                           'triggering':'trw'
                          }
        request = '.active-config.{}.{}.center-freq'.format(self.channel_dict[channel], routing_key_map[self.mode_dict[channel]])
        try:
            self.provider.set(self.queue_dict[channel]+request, cf)
            logger.info('Set central frequency of {} writer for channel {} to {} Hz'.format(self.mode_dict[channel], channel, cf))
            self.freq_dict[channel]=cf
            return True
        except core.exceptions.DriplineError as e:
            if self.mode_testing == True:
                self.freq_dict[channel]=None
                logger.info('Could not set central frequency of Psyllid instance for channel {}'.format(channel))
                return False
            else:
                logger.critical('Could not set central frequency of Psyllid instance for channel {}'.format(channel))
                self.freq_dict[channel]=None
                raise e


    # check psyllid is using monarch
    def is_psyllid_using_monarch(self, channel):
        result =  self.provider.get(self.queue_dict[channel]+'.use-monarch')
        logger.info('Psyllid channel {} is using monarch: {}'.format(channel, result))
        return result


    # tells psyllid to start a run
    # sets duration and filename for this run in psyllid
    def start_run(self, channel, duration, filename):
        payload = {'duration':duration, 'filename':filename}
        self.provider.cmd(self.queue_dict[channel], 'start-run', payload=payload)


    # tells psyllid to stop a run
    # runs will stop automatically after the set duration
    # this method is for interrupting runs
    def stop_run(self, channel):
        self.provider.cmd(self.queue_dict[channel], 'stop-run')


    ### trigger control ###
    # set all trigger parameters at once
    def set_trigger_configuration(self, channel='a', threshold=16, threshold_high=0, n_triggers=1,):
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError("Psyllid instance is not in triggering mode")


        self.set_fmt_snr_threshold( threshold, channel)
        if threshold_high > threshold:
            self.set_fmt_snr_high_threshold( threshold_high, channel)
            self.set_trigger_mode( "two-level-trigger", channel)
        else:
            self.set_trigger_mode( "single-level-trigger", channel)

        self.set_n_triggers( n_triggers, channel)


    # returns all trigger parameters
    def get_trigger_configuration(self, channel='a'):
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError("Psyllid instance is not in triggering mode")

        threshold = self.get_fmt_snr_threshold( channel)
        threshold_high = self.get_fmt_snr_high_threshold( channel)
        n_triggers = self.get_n_triggers( channel)
        trigger_mode = self.get_trigger_mode( channel )

        # threshold_high !> threhold results in trigger_mode = 1
        # threshold_high is not used in this case
        if trigger_mode == "single-level-trigger":
            threshold_high = None

        return {'threshold': threshold, 'threshold_high' : threshold_high, 'n_triggers' : n_triggers}


    # does all time window settings at once
    def set_time_window(self, channel='a', pretrigger_time=2e-3, skip_tolerance=5e-3):
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError("Psyllid instance is not in triggering mode")

        self.set_pretrigger_time( pretrigger_time, channel)
        self.set_skip_tolerance( skip_tolerance, channel)
        self.reactivate(channel)
        self.set_central_frequency(channel, self.freq_dict[channel])


    # returns all time window settings
    def get_time_window(self, channel='a'):
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError("Psyllid instance is not in triggering mode")

        pretrigger_time = self.get_pretrigger_time( channel)
        skip_tolerance = self.get_skip_tolerance( channel)

        return {'pretrigger_time': pretrigger_time, 'skip_tolerance': skip_tolerance}


    # individual time window and trigger parameter sets and gets
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


    def set_trigger_mode(self, mode_id, channel='a'):
        request = '.active-config.{}.fmt.trigger-mode'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, mode_id)
        logger.info('Setting psyllid trigger mode to {} threshold trigger'.format(mode_id))


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


    # tells psyllid to record a frequency mask, write it to a json file and prepare for triggering run
    def make_trigger_mask(self, channel='a', filename='~/fmt_mask.json'):
        if self.mode_dict[channel] != 'triggering':
            logger.error('Psyllid instance is not in triggering mode')
            raise core.exceptions.DriplineGenericDAQError("Psyllid instance is not in triggering mode")

        logger.info('Switch tf_roach_receiver to freq-only')
        request = 'run-daq-cmd.{}.tfrr.freq-only'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)

        logger.info('Switch frequency_mask_trigger to update-mask')
        request = 'run-daq-cmd.{}.fmt.update-mask'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)
        time.sleep(1)

        logger.info('Telling psyllid to not use monarch when starting next run')
        sel.provider.set(self.queue_dict[channel]+'.use-monarch', False)

        logger.info('Start short run to record mask')
        self.start_run(channel ,1000, self.temp_file)
        time.sleep(1)

        logger.info('Write mask to file')
        request = 'run-daq-cmd.{}.fmt.write-mask'.format(str(self.channel_dict[channel]))
        payload = {'filename': filename}
        self.provider.cmd(self.queue_dict[channel], request, payload=payload)

        logger.info('Telling psyllid to use monarch again for next run')
        sel.provider.set(self.queue_dict[channel]+'.use-monarch', True)

        logger.info('Switch tf_roach_receiver back to time and freq')
        request = 'run-daq-cmd.{}.tfrr.time-and-freq'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)

        logger.info('Switch frequency mask trigger to apply-trigger')
        request = 'run-daq-cmd.{}.fmt.apply-trigger'.format(str(self.channel_dict[channel]))
        self.provider.cmd(self.queue_dict[channel],request)
