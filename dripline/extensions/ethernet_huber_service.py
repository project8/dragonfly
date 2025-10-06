import time

from dripline.core import ThrowReply, Entity, calibrate
from dripline.implementations import EthernetSCPIService

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('EthernetHuberService')

def int_to_hexstr(value):
    return hex(value)[2:].zfill(2)

def hexstr_to_bytes(value):
    return bytes.fromhex(value)

def bytes_to_hexstr(value):
    return value.hex()

def hexstr_to_int(value):
    return int(value, 16)

def bytes_to_ints(value):
    return [byte for byte in value]

class EthernetHuberService(EthernetSCPIService):
    '''
    A fairly specific subclass of Service for connecting to ethernet-capable thermo fisher devices.
    In particular, devices must support a half-duplex serial communication with header information, variable length data-payload and a checksum.
    '''
    def __init__(self, **kwargs):
        '''
        Args:
            socket_timeout (int): number of seconds to wait for a reply from the device before timeout.
            socket_info (tuple or string): either socket.socket.connect argument tuple, or string that
                parses into one.
        '''
        EthernetSCPIService.__init__(self, **kwargs)

    def calculate_checksum(self, input_string):
        """
        Calculates the 1-byte checksum of the input string.
        Returns the checksum as a 2-character uppercase hex string.

        :param input_string: The string to compute the checksum for
        :return: Checksum as a hex string (e.g., 'C6')
        """
        total = sum(ord(char) for char in input_string)
        checksum = total % 256
        return f"{checksum:02X}"
    
    def check_checksum(self, cmd):
        # calculate checksum of response except checksum and check if match checksum
        return self.calculate_checksum( cmd[:-2] ) == cmd[-2:]


    def _assemble_cmd(self, cmd_in):
        cmd_raw = cmd_in.split(" ")[0]
        data = " ".join(cmd_in.split(" ")[1:])
        cmd = "[M01" + cmd_raw
        length = len(cmd) + len(data) + 2
        cmd = cmd + f"{length:02X}" + data
        cs = self.calculate_checksum(cmd)
        cmd = cmd + cs + self.command_terminator
        return cmd

    def _extract_reply(self, response, cmd):
        if not self.calculate_checksum(response[:-2]) == response[-2:]:
            logger.warning("Checksum not matching")
        if not response[:4] == "[S01":
            logger.warning("Header not matching")
        if not response[4] == cmd:
            logger.warning("cmd is not matching")
        if not int(response[5:7], 16) == len(response)-2:
            logger.warning("length not matching")
        return response[7:-2]

    def _send_commands(self, commands):
        '''
        Take a list of commands, send to instrument and receive responses, do any necessary formatting.

        commands (list||None): list of command(s) to send to the instrument following (re)connection to the instrument, still must return a reply!
                             : if impossible, set as None to skip
        '''
        all_data=[]

        for cmd in commands:
            command = self._assemble_cmd(cmd)
            logger.debug(f"sending: {command.encode()}")
            self.socket.send(command.encode())
            if command == self.command_terminator:
                blanck_command = True
            else:
                blanck_command = False

            data = self._listen(blanck_command)
            
            if self.reply_echo_cmd:
                if data.startswith(command):
                    data = data[len(command):]
                elif not blank_command:
                    raise ThrowReply('device_error_connection', f'Bad ethernet query return: {data}')
            logger.info(f"sync: {repr(command)} -> {repr(data)}")
            data = self._extract_reply(data, cmd.split(" ")[0])
            all_data.append(data)
        return all_data


__all__.append("HuberEntity")
class HuberEntity(Entity):
    '''
    A endpoint of a Huber device that returns the request result
    '''

    def __init__(self,
                 get_str=None,
                 offset=0,
                 nbytes=-1,
                 numeric=False,
                 **kwargs):
        '''
        Args:
            get_str: hexstring of the command, e.g. 20
        '''
        if get_str is None:
            raise ValueError('<get_str is required to __init__ ThermoFisherHexGetEntity instance')
        else:
            self.cmd_str = get_str
        self.offset = offset
        self.nbytes = nbytes
        self.numeric = numeric
        Entity.__init__(self, **kwargs)

    def convert_to_float(self, hex_str):
        val = int(hex_str, 16)
        if val > int("7FFF", 16):
            val = val - int("FFFF", 16) - 1
        return val/100.

    @calibrate()
    def on_get(self):
        # setup cmd here
        to_send = [self.cmd_str]
        logger.debug(f'Send cmd in hexstr: {to_send[0]}')
        result = self.service.send_to_device(to_send)
        logger.debug(f'raw result is: {result}')
        result = result[self.offset: self.offset+self.nbytes]
        if self.numeric:
            logger.debug("is numeric")
            result = self.convert_to_float(result)
        logger.debug(f'extracted result is: {result}')
        return result

    def on_set(self, value):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support set")
