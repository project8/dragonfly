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
                 **kwargs):

        core.Provider.__init__(self, **kwargs)        
        self.queue_dict = {'a':queue_a, 'b':queue_b, 'c':queue_c}
        self._set_condition_list = set_condition_list
        self.status_dict = {'a':None, 'b':None, 'c':None}
        self.status_value_dict = {'a':None, 'b':None, 'c':None}
        self.channel_dict = {'a': 'ch0', 'b': 'ch1', 'c': 'ch2'}
        self.freq_dict = {'a': None, 'b': None, 'c': None}
        self.mode_dict = {'a':None, 'b':None, 'c':None}


    def _finish_configure(self):
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
                except Exception as e:
                    logger.error('Unexpected error during startup')
                    raise 

        # Summary after startup
        logger.info('Status of channels: {}'.format(self.status_value_dict))
        logger.info('Set central frequencies: {}'.format(self.freq_dict))
        logger.info('Streaming or triggered mode: {}'.format(self.mode_dict))


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
            raise
        else:
            self.status_dict[channel] = result['server']['status']
            self.status_value_dict[channel] = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status_dict[channel]))
            logger.info('Status in numbers: {}'.format(self.status_value_dict[channel]))
            return self.status_value_dict[channel]


    def get_acquisition_mode(self, channel):
        if self.freq_dict[channel]!=None:
            cf = self.freq_dict[channel]
        else:
            cf = 800e6
        self.mode_dict[channel]='streaming'
        if self.set_central_frequency(channel=channel, cf=cf)==False:
           logger.info('Psyllid is not in streaming mode')
           self.mode_dict[channel]='triggered'
           if self.set_central_frequency(channel=channel, cf=cf)==False:
                self.mode_dict[channel]=None
                logger.info('Psyllid is not in triggered mode')
        return self.mode_dict[channel]


    def activate(self, channel):
        if self.status_value_dict[channel] == 0:
            logger.info('Activating Psyllid instance for channel {}'.format(channel))
            self.provider.cmd(self.queue_dict[channel], 'activate-daq')
        else:
            logger.warning('Cannot activate Psyllid instance of channel {}'.format(channel))
            return False
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=4:
            logger.warning('Activating failed')
            return False
        else:
            return True


    def deactivate(self, channel):
        if self.status_value_dict[channel] != 0:
            logger.info('Deactivating Psyllid instance of channel {}'.format(channel))
            self.provider.cmd(self.queue_dict[channel],'deactivate-daq')
        else:
            logger.warning('Cannot deactivate Psyllid instance of channel {}'.format(channel))
            return False
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=0:
            logger.warning('Deactivating failed')
            return False
        else:
            return True


    def reactivate(self, channel):
        if self.status_value_dict[channel] == 4:
            logger.info('Reactivating Psyllid instance of channel {}'.format(channel))
            self.provider.cmd(self.queue_dict[channel], 'reactivate-daq')
            logger.info(result)
        else:
            logger.warning('Cannot reactivate Psyllid instance of channel {}'.format(channel))
            return False
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=4:
            logger.warning('Reactivating failed')
            return False
        else:
            return True


    def quit_psyllid(self, channel):
        self.provider.cmd(self.queue_dict[channel], 'quit-psyllid')
        logger.info('psyllid quit!')


    @property
    def all_central_frequencies(self):
        return self.freq_dict


    def get_central_frequency(self, channel):
        routing_key_map = {
                           'streaming':'strw',
                           'triggered':'trw'
                          }
        request = 'active-config.{}.{}'.format(self.channel_dict[channel], routing_key_map[self.mode_dict[channel]])
        result = self.provider.get(self.queue_dict[channel]+'.'+request)
        logger.info('Psyllid says cf is {}'.format(result['center-freq']))
        self.freq_dict[channel]=result['center-freq']
        return self.freq_dict[channel]

    

    def set_central_frequency(self, channel, cf):
        #logger.info('Trying to set cf of channel {} to {}'.format(channel, cf))
        routing_key_map = {
                           'streaming':'strw',
                           'triggered':'trw'
                          }
        request = '.active-config.{}.{}.center-freq'.format(self.channel_dict[channel], routing_key_map[self.mode_dict[channel]])
        try:
            self.provider.set(self.queue_dict[channel]+request, cf)
            logger.info('Set central frequency of {} writer for channel {} to {} Hz'.format(self.mode_dict[channel], channel, cf))
            self.freq_dict[channel]=cf
            return True

        except core.exceptions.DriplineError:
            logger.error('Could not set central frequency of Psyllid instance for channel {}'.format(channel))
            self.freq_dict[channel]=None
            return False
        except Exception as e:
            logger.error('Unexpected error in set_central_frequency')
            return False 


    def start_run(self, channel, duration, filename):
        payload = {'duration':duration, 'filename':filename}
        self.provider.cmd(self.queue_dict[channel], 'start-run', payload=payload)


    def stop_run(self, channel):
        self.provider.cmd(self.queue_dict[channel], 'stop-run')


    @property
    def number_of_channels(self):
        active_channels = [i for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        logger.info('Active channels are {}'.format(active_channels))
        return len(active_channels)


    @property
    def active_channels(self):
        active_channels = [i for i in self.status_value_dict.keys() if self.status_value_dict[i]==4]
        return active_channels

    # this method counts how many streams (stremaing or triggered) are set up in a psyllid instance. 
    # If we trust that we don't mix up multi stream and single stream config files in the furture we dont need it
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
                    self.mode_dict[channel]='triggered'
                except core.exceptions.DriplineError:
                    pass  
        logger.info('Number of streams for channel {}: {}'.format(channel, stream_count))
        return stream_count


    def set_trigger_configuration(self, threshold=16, threshold_high=0, n_triggers=1, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False

        threshold = self.set_fmt_snr_threshold( threshold, channel)
        threshold_high = self.set_fmt_snr_high_threshold( threshold_high, channel)
        n_triggers = self.set_n_triggers( n_triggers, channel)

        # threshold_high = 0 means it is not used
        if threshold_high == 0:
            threshold_high = None

        return {'threshold': threshold, 'threshold_high' : threshold_high, 'n_triggers' : n_triggers}


    def get_trigger_configuration(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False

        threshold = self.get_fmt_snr_threshold( channel)
        threshold_high = self.get_fmt_snr_high_threshold( channel)
        n_triggers = self.get_n_triggers( channel)

        # threshold_high = 0 means it is not used
        if threshold_high == 0:
            threshold_high = None

        return {'threshold': threshold, 'threshold_high' : threshold_high, 'n_triggers' : n_triggers}


    def set_time_window(self, pretrigger_time=2e-3, skip_tolerance=5e-3, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False

        pretrigger_time = self.set_pretrigger_time( pretrigger_time, channel)
        skip_tolerance = self.set_skip_tolerance( skip_tolerance, channel)

        return {'pretrigger_time': pretrigger_time, 'skip_tolerance': skip_tolerance}


    def get_time_window(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False

        pretrigger_time = self.get_pretrigger_time( channel)
        skip_tolerance = self.get_skip_tolerance( channel)

        return {'pretrigger_time': pretrigger_time, 'skip_tolerance': skip_tolerance}



    def set_pretrigger_time(self, pretrigger_time, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        n_pretrigger_packets = int(round(pretrigger_time/4.096e-5))
        logger.info('Setting psyllid pretrigger to {} packets'.format(n_pretrigger_packets))
        request = '.active-config.{}.eb.pretrigger'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, n_pretrigger_packets)
        return self.get_pretrigger_time(channel)


    def get_pretrigger_time(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.eb.pretrigger'.format(str(self.channel_dict[channel]))
        n_pretrigger_packets = self.provider.get(self.queue_dict[channel]+request)['pretrigger']
        return n_pretrigger_packets *4.096e-5


    def set_skip_tolerance(self, skip_tolerance, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        n_skipped_packets = int(round(skip_tolerance/4.096e-5))
        logger.info('Setting psyllid skip tolerance to {} packets'.format(n_skipped_packets))
        request = '.active-config.{}.eb.skip-tolerance'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, n_skipped_packets)
        return self.get_skip_tolerance(channel)


    def get_skip_tolerance(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.eb.skip-tolerance'.format(str(self.channel_dict[channel]))
        n_skipped_packets = self.provider.get(self.queue_dict[channel]+request)['skip-tolerance']
        return n_skipped_packets*4.096e-5


    def set_fmt_snr_threshold(self, snr, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.fmt.threshold-power-snr'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, snr)
        logger.info('Setting psyllid power snr threshold to {}'.format(snr))
        return self.get_fmt_snr_threshold(channel)


    def get_fmt_snr_threshold(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.fmt.threshold-power-snr'.format(str(self.channel_dict[channel]))
        snr = self.provider.get(self.queue_dict[channel]+request)['threshold-power-snr']
        return snr


    def set_fmt_snr_high_threshold(self, snr, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.fmt.threshold-power-snr-high'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, snr)
        logger.info('Setting psyllid power snr threshold to {}'.format(snr))
        return self.get_fmt_snr_high_threshold(channel)


    def get_fmt_snr_high_threshold(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.fmt.threshold-power-snr-high'.format(str(self.channel_dict[channel]))
        snr = self.provider.get(self.queue_dict[channel]+request)['threshold-power-snr-high']
        return snr


    def set_n_triggers(self, n_triggers, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.eb.n-triggers'.format(str(self.channel_dict[channel]))
        self.provider.set(self.queue_dict[channel]+request, n_triggers)
        logger.info('Setting psyllid n-trigger/skip-tolerance to {}'.format(n_triggers))
        return self.get_n_triggers(channel)


    def get_n_triggers(self, channel='a'):
        if self.mode_dict[channel] != 'triggered':
            logger.warning('Psyllid not in triggered mode')
            return False
        request = '.active-config.{}.eb.n-triggers'.format(str(self.channel_dict[channel]))
        n_triggers = self.provider.get(self.queue_dict[channel]+request)['n-triggers']
        return n_triggers



    def make_trigger_mask(self, channel='a', filename='~/fmt_mask.json'):
        if self.mode_dict[channel] == 'streaming':
            return False

        logger.info('Switch tf_roach_receiver to freq-only')
        request = 'run-daq-cmd.{}.tfrr.freq-only'.format(str(self.channel_dict[channel]))
        result = self.provider.cmd(self.queue_dict[channel],request)

        logger.info('Switch frequency_mask_trigger to update-mask')
        request = 'run-daq-cmd.{}.fmt.update-mask'.format(str(self.channel_dict[channel]))
        result = self.provider.cmd(self.queue_dict[channel],request)
        time.sleep(1)

        logger.info('Start short run to record mask')
        self.start_run(channel ,1000, '/home/project8/fmt_update.egg')
        time.sleep(1)

        logger.info('Write mask to file')
        request = 'run-daq-cmd.{}.fmt.write-mask'.format(str(self.channel_dict[channel]))
        payload = {'filename': filename}
        result = self.provider.cmd(self.queue_dict[channel], request, payload=payload)

        logger.info('Switch tf_roach_receiver back to time and freq')
        request = 'run-daq-cmd.{}.tfrr.time-and-freq'.format(str(self.channel_dict[channel]))
        result = self.provider.cmd(self.queue_dict[channel],request)

        logger.info('Switch frequency mask trigger to apply-trigger')
        request = 'run-daq-cmd.{}.fmt.apply-trigger'.format(str(self.channel_dict[channel]))
        result = self.provider.cmd(self.queue_dict[channel],request)
        return True 
