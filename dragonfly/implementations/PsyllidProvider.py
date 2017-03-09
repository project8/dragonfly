'''
'''

from __future__ import absolute_import

# standard imports
import logging
import uuid
import time
import os
import json
from datetime import datetime

# internal imports
from dripline import core
from dragonfly.implementations import EthernetProvider


__all__ = []

logger = logging.getLogger(__name__)

__all__.append('PsyllidProvider')
class PsyllidProvider(core.Provider, core.Spime):
    '''
    
    '''
    def __init__(self,
                 psyllid_queue='psyllid',
                 set_condition_list = [],
                 **kwargs):

	core.Provider.__init__(self, **kwargs)        
        self.psyllid_queue = psyllid_queue
        self._set_condition_list = set_condition_list
        self.status = None
        self.status_value = None
               
        self.channel_dict = {'a': 0, 'b': 1, 'c': 2}
        self.freq_dict = {'a': None, 'b': None, 'c': None}
        
        
    def _finish_configure(self):
        self.request_status()
        self.set_default_central_frequencies()
        self.get_number_of_streams()
        
        
    def set_default_central_frequencies(self):
        freq_dict = {'a': 800e6, 'b': 800e6, 'c': 800e6}
        self.set_all_central_frequencies(freq_dict)
        

    def request_status(self):
        logger.info('Checking Psyllid status')
        
        try:
            result = self.provider.get(self.psyllid_queue+'.daq-status', timeout=10)
            self.status = result['server']['status']
            self.status_value = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status))
            logger.info('Status in numbers: {}'.format(self.status_value))
            return self.status_value

        except:
            logger.warning('Psyllid is not running or sth. else is wrong')
            self.status=None
            self.status_value=None
            logger.info('Status is {}'.format(self.status))
            return self.status_value
    
    def activate(self):
        logger.info('Trying to activate Psyllid. Status value is {}'.format(self.status_value))
        if self.status_value == 6:
            self.request_status()
        if self.status_value == 0:
            logger.info('Activating Psyllid')
            result = self.provider.cmd(self.psyllid_queue, 'activate-daq')
            self.request_status()
        else:
            logger.warning('Cannot activate Psyllid')
            return False
        if self.status_value != 4:
            logger.error('Could not activate Psyllid')
            return False 
        else: return True


    def deactivate(self):
        if self.status != 0:
            logger.info('Deactivating Psyllid')
            result = self.provider.cmd(self.psyllid_queue,'deactivate-daq')
            self.request_status()
        if self.status_value!=0:
            logger.warning('Could not deactivate Psyllid')
            return False
        else: return True


    def reactivate(self):
        if self.status_value != 0:
            logger.info('Reactivating Psyllid')
            result = self.provider.cmd(self.psyllid_queue, 'reactivate-daq')
            self.request_status()
            return True
        elif self.status_value==0:
	    self.activate()
        else:
             logger.warning('Could not reactivate Psyllid')
             return False


    def quit_psyllid(self):
        result = self.provider.cmd(self.psyllid_queue, 'quit-psyllid')
        logger.info('psyllid quit')

        
    def get_all_central_frequencies(self):
        return self.freq_dict
    

    def set_central_frequency(self, channel='a', cf=800e6):
        cf_in_MHz = round(cf*10**-6)
	
        try:
            request = '.active-config.ch'+str(self.channel_dict[channel])+'.strw.center-freq'
            logger.info(request)
            result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
            logger.info('Set central frequency of streaming writer for channel {} to {} MHz'.format(channel, cf_in_MHz))
            self.freq_dict[channel]=cf
            return True
        except:
            try:
                request = '.active-config.ch'+str(self.channel_dict[channel])+'.ew.center-freq'
                result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                logger.info('Set central frequency of egg writer for channel {} to {} MHz'.format(channel, cf_in_MHz))
                self.freq_dict[channel]=cf
                return True
            except:
                logger.error('Could not set central frequency')
                return False
        
    def set_all_central_frequencies(self, freq_dict):
        for ichannel in freq_dict.keys():
	    self.set_central_frequency(channel=ichannel, cf=freq_dict[ichannel])


    def start_run(self, duration, filename):
        if duration ==0:
            return False
        payload = {'duration':duration, 'filename':filename}
        result = self.provider.cmd(self.psyllid_queue, 'start-run', payload=payload)
        return True
    
    def get_number_of_streams(self):
        active_channels = [i for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        logger.info('Active channels are {}'.format(active_channels))
        return len(active_channels)
        
    def get_active_streams(self):
        active_channels = [i for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        return active_channels
        
__all__.append('MultiPsyllidProvider')
class MultiPsyllidProvider(core.Provider, core.Spime):
    '''
    
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
               
        self.channel_dict = {'a': 0, 'b': 1, 'c': 2}
        self.freq_dict = {'a': None, 'b': None, 'c': None}
        
        
    def _finish_configure(self):
        for i in self.channel_dict.keys():
            try:
                self.request_status(i)
                self.set_central_frequency(channel=i, cf=800e6)
                if self.get_number_of_streams(i)>1:
                    raise core.DriplineGenericDaqError("Psyllid instance for channel {} has too many streams".format(i))
            except:
                logger.info('No Psyllid instance for channel {} present'.format(i))
        logger.info('Status of channels {}'.format(self.status_value_dict))
        logger.info('Set central frequencies {}'.format(self.freq_dict))


    def request_status(self, channel):
        logger.info('Checking Psyllid status of channel {}'.format(channel))
        try:
            result = self.provider.get(self.queue_dict[channel]+'.daq-status', timeout=10)
            logger.info(result)
            self.status_dict[channel] = result['server']['status']
            self.status_value_dict[channel] = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status_dict[channel]))
            logger.info('Status in numbers: {}'.format(self.status_value_dict[channel]))
            return self.status_value_dict[channel]

        except:
            logger.warning('Psyllid instance for channel {} is not running or sth. else is wrong'.format(channel))
            self.status_dict[channel]=None
            self.status_value_dict[channel]=None
            return False
    
    def activate(self, channel):
        if self.status_value_dict[channel] == 0:
            logger.info('Activating Psyllid for channel {}'.format(channel))
            result = self.provider.cmd(self.queue_dict[channel], 'activate-daq')
        else:
            logger.warning('Cannot activate Psyllid')
            return False
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
            logger.warning('Cannot not deactivate Psyllid instance of channel {}'.format(channel))
            return False
        self.request_status(channel)
        if self.status_value_dict[channel]!=0:
            logger.warning('Deactivating failed')
            return False
        else: return True


    def reactivate(self, channel):
        if self.status_value_dict[channel] != 0:
            logger.info('Reactivating Psyllid instance of channel {}'.format(channel))
            result = self.provider.cmd(self.queue_dict[channel], 'reactivate-daq')
            logger.info(result)
        elif self.status_value_dict[channel]==0:
	    self.activate(channel)
        else:
            logger.warning('Cannot not reactivate Psyllid instance of channel {}'.format(channel))
            return False
        self.request_status(channel)
        if self.status_value_dict[channel]!=4:
            logger.warning('Reactivating failed')
            self.freq_dict[channel]=None
            return False
        else:
            return True


    def quit_psyllid(self, channel):
        result = self.provider.cmd(self.queue_dict[channel], 'quit-psyllid')
        logger.info('psyllid quit!')

        
    def get_all_central_frequencies(self):
        return self.freq_dict
    

    def set_central_frequency(self, channel, cf):
        cf_in_MHz = round(cf*10**-6)
	logger.info('Trying to set cf of channel {} to {} MHz'.format(channel, cf_in_MHz))
        if False:
            request = '.active-config.ch'+str(self.channel_dict[channel])+'.strw.center-freq'
            payload_cf = {'center-freq': cf_in_MHz}
            result = self.provider.set(self.queue_dict[channel]+request, cf_in_MHz)
            logger.info('Set central frequency of streaming writer for channel {} to {} MHz'.format(channel, cf_in_MHz))
            self.freq_dict[channel]=cf
            return True
        else:
            if True:
                request = 'active-config.ch'+str(self.channel_dict[channel])+'.ew.center-freq'
                payload = {'center-freq':cf_in_MHz}
                result = self.provider.set(self.queue_dict[channel]+'.'+request, cf_in_MHz)
                logger.info('Set central frequency of egg writer for channel {} to {} MHz'.format(channel, cf_in_MHz))
                self.freq_dict[channel]=cf
		return True
            else:
                logger.error('Could not set central frequency')
                self.freq_dict[channel]=None
                return False

        #return self.reactivate(channel)

    
    
    def start_run(self, channel, duration, filename):
        if duration <= 10:
            return False
        payload = {'duration':duration, 'filename':filename}
        result = self.provider.cmd(self.queue_dict[channel], 'start-run', payload=payload)
        return True
    
    def get_number_of_channels(self):
        active_channels = [i for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        logger.info('Active channels are {}'.format(active_channels))
        return len(active_channels)
        
    def get_channels(self):
        active_channels = [i for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        return active_channels


    def get_number_of_streams(self, channel):
        channel_count = 0
        try:
            cf_in_MHz = round(self.freq_dict[channel])*10**-6
            request = '.node-config.ch'+str(self.channel_dict[channel])+'.strw.center-freq'
            logger.info(request)
            result = self.provider.set(self.queue_dict[channel]+request, cf_in_MHz)
            channel_count += 1
        except:
            try:
                request = '.node-config.ch'+str(self.channel_dict[channel])+'.ew.center-freq'
                result = self.provider.set(self.queue_dict[channel]+request, cf_in_MHz)
                channel_count += 1
            except:
                pass        
        logger.info('Number of streams: {}'.format(channel_count))
        return channel_count
