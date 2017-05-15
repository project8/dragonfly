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


__all__.append('MultiPsyllidProvider')
class MultiPsyllidProvider(core.Provider):
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
                self.mode_dict[channel]='streaming'

                try: 
                    if self.set_central_frequency(channel=channel, cf=800e6)==False:
                       self.mode_dict[channel]='triggered'
                       if self.set_central_frequency(channel=channel, cf=800e6)==False:
                            self.mode_dict[channel]=None
                            raise core.exceptions.DriplineGenericDAQError("Stream writer of Psyllid instance for channel {} is not configured correctly".format(channel))

                    if self.get_number_of_streams(channel)!=1:
                        self.mode_dict[channel]=None
                        raise core.exceptions.DriplineGenericDAQError("Streams of Psyllid instance for channel {} are not configured correctly".format(channel))

                except core.exceptions.DriplineGenericDAQError:
                    logger.warning('No matching Psyllid instance for channel {} present'.format(channel))

        # Summary after startup
        logger.info('Status of channels: {}'.format(self.status_value_dict))
        logger.info('Set central frequencies: {}'.format(self.freq_dict))
        logger.info('Streaming or triggered mode: {}'.format(self.mode_dict))


    def request_status(self, channel):
        logger.info('Checking Psyllid status of channel {}'.format(channel))
        try:
            result = self.provider.get(self.queue_dict[channel]+'.daq-status', timeout=10)
        except:
            logger.warning('Psyllid instance for channel {} is not running or sth. else is wrong'.format(channel))
            self.status_dict[channel]=None
            self.status_value_dict[channel]=None
            return self.status_value_dict[channel]
        else:
            self.status_dict[channel] = result['server']['status']
            self.status_value_dict[channel] = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status_dict[channel]))
            logger.info('Status in numbers: {}'.format(self.status_value_dict[channel]))
            return self.status_value_dict[channel]



    def activate(self, channel):
        if self.status_value_dict[channel] == 0:
            logger.info('Activating Psyllid instance for channel {}'.format(channel))
            result = self.provider.cmd(self.queue_dict[channel], 'activate-daq')
        else:
            logger.warning('Cannot activate Psyllid instance of channel {}'.format(channel))
            return False
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=4:
            logger.warning('Activating failed')
            return False
        else: return True


    def deactivate(self, channel):
        if self.status_value_dict[channel] != 0:
            logger.info('Deactivating Psyllid instance of channel {}'.format(channel))
            result = self.provider.cmd(self.queue_dict[channel],'deactivate-daq')
        else:
            logger.warning('Cannot deactivate Psyllid instance of channel {}'.format(channel))
            return False
        time.sleep(1)
        self.request_status(channel)
        if self.status_value_dict[channel]!=0:
            logger.warning('Deactivating failed')
            return False
        else: return True


    def reactivate(self, channel):
        if self.status_value_dict[channel] == 4:
            logger.info('Reactivating Psyllid instance of channel {}'.format(channel))
            result = self.provider.cmd(self.queue_dict[channel], 'reactivate-daq')
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
        result = self.provider.cmd(self.queue_dict[channel], 'quit-psyllid')
        logger.info('psyllid quit!')


    @property
    def all_central_frequencies(self):
        return self.freq_dict


    def get_central_frequency(self, channel):
        if self.mode_dict[channel] == 'streaming':
            request = 'active-config.'+self.channel_dict[channel]+'.strw'
            result = self.provider.get(self.queue_dict[channel]+'.'+request)
            logger.info('Psyllid says cf is {}'.format(result['center-freq']))
            self.freq_dict[channel]=result['center-freq']
            return self.freq_dict[channel]
        if self.mode_dict[channnel] == 'triggered':
            request = 'active-config.'+self.channel_dict[channel]+'.trw'
            result = self.provider.get(self.queue_dict[channel]+'.'+request)
            logger.info('Psyllid says cf is {}'.format(result['center-freq']))
            self.freq_dict[channel]=result['center-freq']
            return self.freq_dict[channel]

    

    def set_central_frequency(self, channel, cf):
        #logger.info('Trying to set cf of channel {} to {}'.format(channel, cf))
        try:
            if self.mode_dict[channel] == 'streaming':
                request = '.active-config.'+self.channel_dict[channel]+'.strw.center-freq'
                result = self.provider.set(self.queue_dict[channel]+request, cf)
                logger.info('Set central frequency of streaming writer for channel {} to {} Hz'.format(channel, cf))
                self.freq_dict[channel]=cf
                return True

            elif self.mode_dict[channel] == 'triggered':
                request = 'active-config.ch'+self.channel_dict[channel]+'.trw.center-freq'
                result = self.provider.set(self.queue_dict[channel]+'.'+request, cf)
                logger.info('Set central frequency of egg writer for channel {} to {} Hz'.format(channel, cf))
                self.freq_dict[channel]=cf
                return True
            else:
                return False
        except:
            logger.error('Could not set central frequency')
            self.freq_dict[channel]=None
            return False


    def start_run(self, channel, duration, filename):
        payload = {'duration':duration, 'filename':filename}
        result = self.provider.cmd(self.queue_dict[channel], 'start-run', payload=payload)


    def stop_run(self, channel):
        result = self.provider.cmd(self.queue_dict[channel], 'stop-run')


    @property
    def number_of_channels(self):
        active_channels = [i for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        logger.info('Active channels are {}'.format(active_channels))
        return len(active_channels)


    @property
    def active_channels(self):
        active_channels = [i for i in self.status_value_dict.keys() if self.status_value_dict[i]==4]
        return active_channels


    def get_number_of_streams(self, channel):
        stream_count = 0
        for i in range(3):
            try:
                request = '.node-config.ch'+str(i)+'.strw'
                result = self.provider.get(self.queue_dict[channel]+request)
                stream_count += 1
                self.mode_dict[channel]='streaming'
            except:
                try:
                    request = '.node-config.ch'+str(i)+'.trw'
                    result = self.provider.get(self.queue_dict[channel]+request)
                    stream_count += 1
                    self.mode_dict[channel]='triggered'
                except:
                    pass  
        logger.info('Number of streams for channel {}: {}'.format(channel, stream_count))
        return stream_count


    def set_fmt_snr_threshold(self, channel='a', snr=6):
        if self.mode_dict[channel] == 'streaming':
            logger.warning('Psyllid not in streaming mode')
            return False
        request = '.node-config.ch'+str(self.channel_dict[channel])+'.fmt.threshold-power-snr'
        result = self.provider.set(self.queue_dict[channel]+request, snr)
        self.deactivate(channel)
        time.sleep(1)
        self.activate(channel)
        return True


    def make_trigger_mask(self, channel='a', filename='~/fmt_mask.json'):
        if self.mode_dict[channel] == 'streaming':
            return False

        self.request_status(channel)
        if self.status_value_dict[channel] !=4:
            self.activate(channel)

        logger.info('freq-only')
        request = 'run-daq-cmd.ch'+str(self.channel_dict[channel])+'.tfrr.freq-only'
        result = self.provider.cmd(self.queue_dict[channel],request)

        logger.info('update-mask')
        request = 'run-daq-cmd.ch'+str(self.channel_dict[channel])+'.fmt.update-mask'
        result = self.provider.cmd(self.queue_dict[channel],request)
        time.sleep(1)

        logger.info('run')
        request = 'start-run'
        result = self.provider.cmd(self.queue_dict[channel], request)
        time.sleep(1)

        logger.info('write-mask')
        request = 'run-daq-cmd.ch'+str(self.channel_dict[channel])+'.fmt.write-mask'
        payload = {'filename': filename}
        result = self.provider.cmd(self.queue_dict[channel], request, payload=payload)

        logger.info('back to time and freq')
        request = 'run-daq-cmd.ch'+str(self.channel_dict[channel])+'.tfrr.time-and-freq'
        result = self.provider.cmd(self.queue_dict[channel],request)

        logger.info('apply-trigger')
        request = 'run-daq-cmd.ch'+str(self.channel_dict[channel])+'.fmt.apply-trigger'
        result = self.provider.cmd(self.queue_dict[channel],request)
        return True 
