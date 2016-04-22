from __future__ import absolute_import
import socket
import threading
import types

from dripline.core import Provider, Endpoint
from dragonfly.implementations import EthernetProvider
from dragonfly.implementations import MuxerGetSpime
from dripline.core.utilities import fancy_doc
from dripline.core import exceptions

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('MuxerProvider')
@fancy_doc
# Defining new class MuxerProvider that inherits from EthernetProvider
class MuxerProvider(EthernetProvider):

        def __init__(self, scan_interval=0,**kwargs): # Adding scan_interval parameter 
                '''
                scan_interval (int): time between scans in seconds
                '''
                EthernetProvider.__init__(self,**kwargs)
                if scan_interval == 0:
                        raise ValueError("scan interval must be > 0")
                self.scan_interval = scan_interval

        # Function to configure channels
        def conf_scan_list(self, *args, **kwargs):
                '''
                conf_scan_list loops over the provider's internal list of endpoints and attempts to configure each		
                '''

                ch_scan_list = list() # Initiate an empty scan list to be populated

                self.send(["ABOR"]) # Stop the current scan

                # Loop over the endpoints
                for child in self.endpoints:
                        # Only "MuxerGetSpime" endpoints are considered for scan list
                        if not isinstance(child, MuxerGetSpime):
                                continue # If not of this type, go onto the next 
                        else:
                                if child.conf_str == None: # If no configuration string is given (initiated as None)
                                        raise exceptions.DriplineValueError('conf_str value is required to configure {}'.format(child.name)) # Raise an exception to user
                                        raise exceptions.DriplineWarning('if {} is not to be configured, please set conf_str to False'.format(child.name)) # Raise warning 
                                        continue # Don't configure channel nor add it to the scan list
                                elif child.conf_str == False: # If endpoint conf_str is set to False don't configure channel but do add it to the scan list
                                        ch_scan_list.append(child.ch_number) # Add channel number to scan list
                                        continue 
                                else: # If configuration string present
                                        self.send([child.conf_str.format(child.ch_number)]) # Send the configuration command w/ appropriate channel number 
                                        logger.debug('sending configuration command:\n{}'.format(child.conf_str.format(child.ch_number))) # Debug statement to keep track of things;
                                                                                                                                  # making sure we're sending the correct command
                                        ch_scan_list.append(child.ch_number) # Add channel number to scan list

                # Setting up the scan
                scan_list_cmd = 'ROUT:SCAN (@{})'.format(",".join(ch_scan_list)) # Create scan list command from channel scan list
                logger.debug('sending scan list command:\n{}'.format(scan_list_cmd)) # Making sure we send the right command
                self.start_scan(scan_list_cmd) # Send command to start_scan method 

        # Function to start scan
        def start_scan(self, scan_list_cmd):

                # Send scan command
                self.send([scan_list_cmd])

                # Configure trigger settings
                self.send(["TRIG:SOUR TIM", "TRIG:COUN INF", "TRIG:TIM {}".format(self.scan_interval)])

                # Send the init command to start the scan
                self.send(["INIT"])








