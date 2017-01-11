'''
All communication with instruments is performed via ethernet, or via an intermediate interface that inherits from EthernetProvider.  This class must be kept general, with specific cases handled in higher-level interfaces.

General rules to observe:
- All instruments should communicate with a response_terminator (typically \r and/or \n, possibly an additional prompt)
- All endpoints and communication must be configured to return a response, otherwise nasty timeouts will be incurred

Every instrument config file (hardware repo) must specify:
- socket_info, command_terminator, response_terminator
Optional config options:
- socket timeout   : if long timeouts expected (undesirable)
- cmd_at_reconnect : if instrument response buffer needs clearing or special configuration
- reply_echo_cmd   : if instrument response contains the query (see glenlivet)
- bare_response_terminator : special response terminator (undesirable)
'''
from __future__ import absolute_import
import socket
import threading

from dripline.core import Provider, Endpoint, exceptions, fancy_doc

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('EthernetProvider')
@fancy_doc
class EthernetProvider(Provider):
    def __init__(self,
                 socket_timeout=1.0,
                 socket_info=('localhost',1234),
                 cmd_at_reconnect=['*OPC?'],
                 command_terminator='',
                 response_terminator=None,
                 bare_response_terminator=None,
                 reply_echo_cmd=False,
                 **kwargs
                 ):
        '''
        > Connection-related options:
        socket_timeout (float): time in seconds for the socket to timeout
        socket_info (tuple): (<network_address_as_str>, <port_as_int>)
        cmd_at_reconnect (list): list of command(s) to send to the instrument following (re)connection to the instrument
                               : still must return a reply!
        > Query-related options:
        command_terminator (str): string to append to commands
        response_terminator (str||None): string to strip from responses, this MUST exist for get method to function properly!
        bare_response_terminator (str||None): abbreviated string to strip from responses containing only prompt
                                            : only used to handle non-standard glenlivet/lockin behavior
        reply_echo_cmd (bool): set to True if command+command_terminator or just command are present in reply
        '''
        Provider.__init__(self, **kwargs)

        if isinstance(socket_info, str):
            logger.debug("Formatting socket_info: {}".format(repr(socket_info)))
            import re
            re_str = "\([\"'](\S+)[\"'], ?(\d+)\)"
            (ip,port) = re.findall(re_str,socket_info)[0]
            socket_info = (ip,int(port))
        if response_terminator is None or response_terminator == '':
            raise exceptions.DriplineValueError("Invalid response terminator: <{}>! Expect string".format(repr(response_terminator)))
        if not isinstance(cmd_at_reconnect, list) or len(cmd_at_reconnect)==0:
            raise exceptions.DriplineValueError("Invalid cmd_at_reconnect: <{}>! Expect non-zero length list".format(repr(cmd_at_reconnect)))

        self.alock = threading.Lock()
        self.socket = socket.socket()
        self.socket_timeout = float(socket_timeout)
        self.socket_info = socket_info
        self.cmd_at_reconnect = cmd_at_reconnect
        self.command_terminator = command_terminator
        self.response_terminator = response_terminator
        self.bare_response_terminator = bare_response_terminator
        self.reply_echo_cmd = reply_echo_cmd
        self._reconnect()


    def _reconnect(self):
        '''
        Method establishing socket to ethernet instrument.
        Called by __init__ or send (on failed communication).
        '''
        self.socket.close()
        self.socket = socket.socket()
        try:
            self.socket.connect(self.socket_info)
        except socket.error:
            logger.warning("connection with info: {} refused".format(self.socket_info))
            raise exceptions.DriplineHardwareConnectionError("Unable to establish ethernet socket {}".format(self.socket_info))
        self.socket.settimeout(self.socket_timeout)
        logger.info("Ethernet socket {} established".format(self.socket_info))

        commands = self.cmd_at_reconnect
        while commands[0] is None:
            logger.debug("Emptying reconnect buffer")
            commands.pop(0)
            self._listen(blank_command=True)
        response = self._send_commands(self.cmd_at_reconnect)
        if response[-1] != '1':
            logger.warning("Failed connection test.  Response was {}".format(response))
            self.socket.close()
            raise exceptions.DriplineHardwareConnectionError("Failed connection test.")


    def send(self, commands, **kwargs):
        '''
        Standard provider method to communicate with instrument.
        NEVER RENAME THIS METHOD!
        '''
        if isinstance(commands, str):
            commands = [commands]
        self.alock.acquire()

        try:
            data = self._send_commands(commands)
        except (socket.error, exceptions.DriplineHardwareResponselessError):
            logger.warning("Attempting socket reconnect")
            self._reconnect()
            data = self._send_commands(commands)
        finally:
            self.alock.release()
        to_return = ';'.join(data)
        logger.debug("should return:\n{}".format(to_return))
        return to_return


    def _send_commands(self, commands):
        '''
        Take a list of commands, send to instrument and receive responses, do
            any necessary formatting.
        '''
        all_data=[]

        for command in commands:
            og_command = command
            command += self.command_terminator
            logger.debug("sending: {}".format(repr(command)))
            self.socket.send(command)
            if command == self.command_terminator:
                blank_command = True
            else:
                blank_command = False

            data = self._listen(blank_command)

            if self.reply_echo_cmd:
                if data.startswith(command):
                    data = data[len(command):]
                elif data.startswith(og_command):
                    data = data[len(og_command):]
                else:
                    logger.warning('Data without reply echo.')
            logger.info("sync: {} -> {}".format(repr(command),repr(data)))
            all_data.append(data)
        return all_data


    def _listen(self, blank_command=False):
        '''
        Query socket for response.
        '''
        data = ''
        try:
            while True:
                data += self.socket.recv(1024)
                if data not in (self.response_terminator, self.bare_response_terminator):
                    if data.endswith(self.response_terminator):
                        terminator = self.response_terminator
                        break
                    # Special exception for bad communication with glenlivet
                    elif self.bare_response_terminator and data.endswith(self.bare_response_terminator):
                        terminator = self.bare_response_terminator
                        break
                # Special exception for disconnect of prologix box to avoid infinite loop
                if data == '':
                    raise exceptions.DriplineHardwareResponselessError("empty socket.recv packet from {}".format(self.socket_info[0]))
        except socket.timeout:
            logger.warning("socket.timeout condition met; received:\n{}".format(repr(data)))
            if blank_command == False and data == '':
                logger.critical("Cannot connect to: {}".format(self.socket_info[0]))
                raise exceptions.DriplineHardwareResponselessError("socket.timeout from {}".format(self.socket_info[0]))
            else:
                logger.critical("socket.timeout condition met with data from {}".format(self.socket_info[0]))
                terminator = ''
        logger.debug(repr(data))
        data = data[0:data.rfind(terminator)]
        return data
