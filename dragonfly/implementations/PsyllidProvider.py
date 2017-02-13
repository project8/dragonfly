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



__all__ = []

logger = logging.getLogger(__name__)

__all__.append('PsyllidProvider')
class PsyllidProvider(core.Provider, core.Spime):
    '''
    
    '''
    def __init__(self,
                 
                 queue=5672
                 set_condition_list = [],
                 **kwargs):
        
        self.broker = broker
        self.psyllid_queue = queue
        self._set_condition_list = set_condition_list
        self.status = None
        self.status_value = None
        self.duration = None
        self.central_frequency = None
        self.multi_channel_daq = False
        
        self.channel_dictionary = {'a': 0, 'b': 1, 'c': 2}
        self.freq_dict = {'a': None, 'b': None, 'c': None}
        
        
    def _finish_configure(self):
        self.request_status()
        self.set_default_central_frequencies
        self.get_number_of_channels()
        
        
    def set_default_central_frequencies(self):
        freq_dict = {'a': 1000e6, 'b': 1000e6, 'c': 1000e6}
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
        if self.status_value == 6:
            self.is_running()
        elif self.status_value == 0:
            logger.info('Activating Psyllid')
            result = self.provider.cmd(self.psyllid_queue, 'activate-daq')
            self.request_status()
            return self.status_value

        else:
            logger.warning('Could not activate Psyllid')
            return False


    def deactivate(self):
        if self.status != 0:
            logger.info('Deactivating Psyllid')
            result = self.provider.cmd(self.psyllid_queue,'deactivate-daq')
            self.request_status()
        if self.status_value!=0:
            logger.warning('Could not deactivate Psyllid')
            return False
        else: return self.status_value


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
    

    def set_central_frequency(self, cf, channel='a'):
        cf_in_Mhz = round(cf*10**-6)
        try:
             request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.strw.center-freq'
             result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
             logger.info('Set central frequency of streaming writer for channel {}'.format(channel))
        except:
            try:
                request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.ew.center-freq'
                result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                logger.info('Set central frequency of egg writer for channel {}'.format(channel))
            except:
                logger.error('Could not set central frequency')

        return self.reactivate()
        
    def set_all_central_frequencies(self, freq_dict):
        for channel in freq_dict.keys():
            cf_in_MHz = round(freq_dict[channel]*10**-6)
            self.freq_dict[channel]=freq_dict[channel]
            try:
                request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.strw.center-freq'
                result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                logger.info('Set central frequency of streaming writer for channel {}'.format(channel))
            except:
                try:
                    request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.ew.center-freq'
                    result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                    logger.info('Set central frequency of egg writer for channel {}'.format(channel))
            	except:
                    logger.error('Could not set central frequency')
                    self.freq_dict[channel]=None
        logger.info('central frequencies: {}'.format(self.freq_dict))
        return self.reactivate()
    
    
    def start_run(self, payload)
        result = self.provider.cmd(self.psyllid_queue, 'start-run', payload=payload)
        
    
    def get_number_of_channels(self):
        active_channels = [self.freq_dict[i] for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        logger.info('Active channels are {}'.format(active_channels.keys()))
        return len(active_channels)
        
    def get_active_channels(self):
        active_channels = [self.freq_dict[i] for i in self.freq_dict.keys() if self.freq_dict[i]!=None]
        return active_channels
        