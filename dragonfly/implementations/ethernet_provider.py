from __future__ import absolute_import
import socket
import threading
import types

from dripline.core import Provider, Endpoint
from dripline.core.utilities import fancy_doc

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('EthernetProvider')
@fancy_doc
class EthernetProvider(Provider):
    def __init__(self,
                 socket_timeout=1.0,
                 socket_info=("localhost",1234),
                 response_terminator = None,
                 command_terminator = None,
                 reply_echo_cmd = False,
                 **kwargs
                 ):
        '''
        socket_timeout (float): time in seconds for the socket to timeout
        socket_info (tuple): (<network_address_as_str>, <port_as_int>)
        response_terminator (str||None): string to rstrip() from responses
        command_terminator (str||None): string to append to commands
        reply_echo_cmd (bool): set to True if command+command_terminator or just command are present in reply
        '''
        Provider.__init__(self, **kwargs)
        self.alock = threading.Lock()
        self.socket_timeout = float(socket_timeout)
        self.socket_info = socket_info
        self.socket = socket.socket()
        self.response_terminator = response_terminator
        self.bare_response_terminator = self.response_terminator[len('\r\n'):] # definition for bare response terminator '34980A>' needed for get()
        self.command_terminator = command_terminator
        self.reply_echo_cmd = reply_echo_cmd
        if type(self.socket_info) is str:
            import re
            re_str = "\([\"'](\S+)[\"'], ?(\d+)\)"
            (ip,port) = re.findall(re_str,self.socket_info)[0]
            self.socket_info = (ip,int(port))
        logger.debug('socket info is {}'.format(self.socket_info))
        self.reconnect()

    def send_commands(self, commands):
        all_data=[]

        for command in commands:
            og_command = command # saving original command
            #if self.command_terminator is not None:
            command += self.command_terminator
            logger.debug('sending: {}'.format(repr(command))) 
            self.socket.send(command)
            data = self.get()
            logger.debug('data from get(): {}'.format(repr(data))) # Added for debugging
            logger.debug('data is of type: {}'.format(type(data))) # Added for debugging
            if self.reply_echo_cmd: # See reply_echo_cmd docstring above
                if data.startswith(command): # Note that command here is original command + command terminator 
                    data = data[len(command):] 
                elif data.startswith(og_command): # If response only include the original command w/o the command terminator
                    data = data[len(og_command):]
            logger.debug('sync: {} -> {}'.format(repr(command),repr(data)))
            all_data.append(data)
        return all_data

    def reconnect(self):
        self.socket.close()
        self.socket = socket.socket()
        try:
            self.socket.connect(self.socket_info)
        except:
            logger.warning('connection with info: {} refused'.format(self.socket_info))
            raise
        self.socket.settimeout(self.socket_timeout)
        # Get these messages out of the way first before sending any other commands
        self.send("") # Machine will respond with it's welcome message+response_terminator

    def send(self, commands):
        '''
        this issues commands
        '''
        if isinstance(commands, types.StringType):
            commands = [commands]
        all_data = []
        self.alock.acquire()
        logger.debug('commands is: {}'.format(commands)) # Added for debugging
        try:
            all_data += self.send_commands(commands)

        except socket.error:
            self.alock.release()
            self.reconnect()
            self.alock.acquire()
            all_data += self.send_commands(commands)

        finally:
            self.alock.release()
        to_return = ';'.join(all_data)
        logger.debug('should return:\n{}'.format(to_return))
        return to_return

    def get(self):
        data = ""
        try:
            while True:
                data += self.socket.recv(1024)
                logger.debug('data received from the socket is: {}'.format(repr(data))) # Added for debugging
                data = data.strip()
                if self.response_terminator:
                    if data.endswith(self.response_terminator):
                        data = data[0:data.find(self.response_terminator)]
                        break
                    elif data.endswith(self.bare_response_terminator):
                        data = data[0:data.find(self.bare_response_terminator)]     
                        break
        except socket.timeout:
            logger.critical('Cannot Connect!')
        if self.response_terminator:
            data = data.rsplit(self.response_terminator,1)[0]
        logger.debug('get() is returning data: {}'.format(repr(data))) # Added for debugging
        logger.debug('data is of type: {}'.format(type(data))) # Added for debugging
        return data

    @property
    def spimes(self):
        return self.endpoints
