from __future__ import absolute_import
import socket
import threading
import types

from dripline.core import Provider, Endpoint, exceptions
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
                 response_terminator=None,
                 bare_response_terminator=None,
                 command_terminator=None,
                 reply_echo_cmd=False,
                 cmd_at_reconnect=None,
                 **kwargs
                 ):
        '''
        socket_timeout (float): time in seconds for the socket to timeout
        socket_info (tuple): (<network_address_as_str>, <port_as_int>)
        response_terminator (str||None): string to strip from responses
        bare_response_terminator (str||None): alternate string to strip from responses; depending on provider's reply
        command_terminator (str||None): string to append to commands
        reply_echo_cmd (bool): set to True if command+command_terminator or just command are present in reply
        cmd_at_start (str||None): command to send to the instrument after the (re)connection to the instrument (must ask for a reply)
        '''
        Provider.__init__(self, **kwargs)
        self.alock = threading.Lock()
        self.socket_timeout = float(socket_timeout)
        self.socket_info = socket_info
        self.socket = socket.socket()
        self.response_terminator = response_terminator
        self.bare_response_terminator = bare_response_terminator
        self.command_terminator = command_terminator
        self.reply_echo_cmd = reply_echo_cmd
        if type(self.socket_info) is str:
            import re
            re_str = "\([\"'](\S+)[\"'], ?(\d+)\)"
            (ip,port) = re.findall(re_str,self.socket_info)[0]
            self.socket_info = (ip,int(port))
        logger.debug('socket info is {}'.format(self.socket_info))
        self.reconnect()


    def send_commands(self, commands, **kwargs):
        all_data=[]

        endpoint_name = None
        endpoint_ch_number = None

        if 'endpoint_name' in kwargs.keys():
            endpoint_name = kwargs['endpoint_name']
        if 'endpoint_ch_number' in kwargs.keys():
            endpoint_ch_number = kwargs['endpoint_ch_number']

        for command in commands:
            og_command = command
            command += self.command_terminator
            logger.debug('sending: {}'.format(repr(command)))
            self.socket.send(command)
            if command == self.command_terminator or command.startswith("++"):
                blank_command = True
            else:
                blank_command = False

            data = self.get(blank_command)

            if self.reply_echo_cmd:
                if og_command == 'SYST:ERR?':
                    if data.startswith(command):
                        error_data = data[len(command):]
                    elif data.startswith(og_command):
                        error_data = data[len(og_command):]
                    if error_data == '+0,"No error"':
                        logger.debug('sync: {} -> {}'.format(repr(command),repr(error_data)))
                        all_data.append(error_data)
                    else:
                        logger.error('error detected; no further commands will be sent')
                        raise exceptions.DriplineHardwareError('{} when attempting to configure endpoint named "{}" with channel number "{}"'.format(error_data,endpoint_name,endpoint_ch_number))
                        break
                else:
                    if data.startswith(command):
                        data = data[len(command):]
                    elif data.startswith(og_command):
                        data = data[len(og_command):]
                    logger.debug('sync: {} -> {}'.format(repr(command),repr(data)))
                    all_data.append(data)
            else:
                if og_command == 'SYST:ERR?':
                    if data == '+0,"No error"':
                        logger.debug('sync: {} -> {}'.format(repr(command),repr(error_data)))
                        all_data.append(error_data)
                    else:
                        logger.error('error detected; no further commands will be sent')
                        raise exceptions.DriplineHardwareError('{} when attempting to configure endpoint named "{}" with channel number "{}"'.format(error_data,endpoint_name,endpoint_ch_number))
                        break
                else:
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
        if isinstance(self.cmd_at_reconnect, types.StringType) and self.cmd_at_reconnect!=None:
            self.send(self.cmd_at_reconnect)
        else:
            self.send("")

    def send(self, commands, **kwargs):
        '''
        this issues commands
        '''
        if isinstance(commands, types.StringType):
            commands = [commands]
        all_data = []
        self.alock.acquire()

        try:
            all_data += self.send_commands(commands, **kwargs)

        except socket.error:
            self.alock.release()
            self.reconnect()
            self.alock.acquire()
            all_data += self.send_commands(commands, **kwargs)

        finally:
            self.alock.release()
        to_return = ';'.join(all_data)
        logger.debug('should return:\n{}'.format(to_return))
        return to_return

    def get(self, blank_command = False):
        data = ""
        try:
            while True:
                data += self.socket.recv(1024)
                if self.response_terminator:
                    if data not in (self.response_terminator,self.bare_response_terminator):
                        if data.endswith(self.response_terminator):
                            data = data[0:data.find(self.response_terminator)]
                            break
                        elif data.endswith(self.bare_response_terminator):
                            data = data[0:data.find(self.bare_response_terminator)]
                            break
                else:
                    break
        except socket.timeout:
            if blank_command == False and data == "":
                logger.critical('Cannot Connect to: ' + self.socket_info[0])
        if self.response_terminator:
            data = data.rsplit(self.response_terminator,1)[0]
        return data

    @property
    def spimes(self):
        return self.endpoints
