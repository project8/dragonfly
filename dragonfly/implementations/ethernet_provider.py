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
                 reply_echo_cmd = True,
                 **kwargs
                 ):
        '''
        socket_timeout (float): time in seconds for the socket to timeout
        socket_info (tuple): (<network_address_as_str>, <port_as_int>)
        response_terminator (str||None): string to rstrip() from responses
        command_terminator (str||None): string to append to commands
        reply_echo_cmd (bool): set to true if command+command_terminator are present in reply
        '''
        Provider.__init__(self, **kwargs)
        self.alock = threading.Lock()
        self.socket_timeout = float(socket_timeout)
        self.socket_info = socket_info
        self.socket = socket.socket()
        self.response_terminator = response_terminator
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
            logger.debug('sending: {}'.format(repr(command)))
            if self.command_terminator is not None:
                command += self.command_terminator
            self.socket.send(command)
            import ipdb
            ipdb.set_trace()
            data = self.get()
            if (data.startswith(command) and self.reply_echo_cmd):
                data = data[0:data.find(self.command_terminator)+len(self.command_terminator)] + data[data.rfind(self.command_terminator)+len(self.command_terminator):]
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
        self.send("")

    def send(self, commands):
        '''
        this issues commands
        '''
        if isinstance(commands, types.StringType):
            commands = [commands]
        all_data = []
        self.alock.acquire()
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
                data = data.strip()
                if (self.response_terminator and  data.endswith(self.response_terminator)):
                        data= data[0:data.find(self.response_terminator)]
                        break
        except socket.timeout:
            logger.critical('Cannot Connect!')
        return data

    @property
    def spimes(self):
        return self.endpoints
