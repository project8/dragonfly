import time

from dripline.core import ThrowReply
from dripline.implementations import EthernetSCPIService

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('EthernetThermoFisherService')

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

class EthernetThermoFisherService(EthernetSCPIService):
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
        self.lead_char = kwargs.pop("lead_char", b'\xcc')
        self.msb = kwargs.pop("msb", b'\x00')
        self.lsb = kwargs.pop("lsb", b'\x01')
 
        if 'cmd_at_reconnect' not in kwargs:
            kwargs['cmd_at_reconnect'] = ['00']
        if 'reconnect_test' not in kwargs:
            kwargs['reconnect_test'] = '0001'
        if 'command_terminator' not in kwargs:
            kwargs['command_terminator'] = ''
        if 'response_terminator' not in kwargs:
            kwargs['response_terminator'] = 'ignored'
        if 'reply_echo_cmd' not in kwargs:
            kwargs['reply_echo_cmd'] = False

        EthernetSCPIService.__init__(self, **kwargs)

    def calculate_checksum(self, command_bytes):
        """
        Calculate the checksum by:
        1. Summing the bytes.
        2. Taking the lower 8 bits (1-byte sum).
        3. Performing bitwise XOR with 0xFF.
        """
        byte_sum = sum(command_bytes) & 0xFF  # Sum and reduce to 1 byte
        checksum = byte_sum ^ 0xFF            # Bitwise inversion
        return checksum
    
    def check_checksum(self, cmd):
        # calculate checksum of response except lead_char and checksum and check if match checksum
        return self.calculate_checksum( cmd[1:-1] ) == cmd[-1]


    def _assemble_cmd(self, cmd_in):
        base_cmd = cmd_in[:2]
        data = cmd_in[2:]
        nDataBytes = len(hexstr_to_bytes(data))
        command = hexstr_to_bytes(base_cmd) + hexstr_to_bytes(int_to_hexstr(nDataBytes)) + hexstr_to_bytes(data)
        logger.debug(f"Assemblind cmd")
        command = self.msb + self.lsb + command
        logger.debug(f"Command is {command} or tpye {type(command)}")
        cs = self.calculate_checksum(command).to_bytes(1, byteorder='big')
        logger.debug(f"Checksum is {cs} of type {type(cs)}")
        command = self.lead_char + command + cs
        return command

    def _send_commands(self, commands):
        '''
        Take a list of commands, send to instrument and receive responses, do any necessary formatting.

        commands (list||None): list of command(s) to send to the instrument following (re)connection to the instrument, still must return a reply!
                             : if impossible, set as None to skip
        '''
        all_data=[]

        for command in commands:
            cmd = self._assemble_cmd(command)

            logger.debug(f"sending: {cmd}")
            self.socket.send(cmd)
            logger.debug("Wait for responds")
            # The device may need some time to reply to the send command.
            # Currently we are using a sleep to make sure the device has enough time to reply.
            # This may not be ideal. An example on how to do it with a for loop,
            # that waits for a message of length N can be found here.
            # https://docs.python.org/2/howto/sockets.html#socket-howto
            # This is an enhancement for the future but currently can not be tested.
            time.sleep(0.1)
            logger.debug("Read header")
            header = self.socket.recv(5)
            nBytes = int(header[-1])
            logger.debug("Read data")
            data = self.socket.recv(nBytes)
            logger.debug("Read checksum")
            check = self.socket.recv(1)
            response = header + data + check
            logger.info(f"Recived: {response}")
            if not self.check_checksum(response):
                raise ThrowReply("checksum_error", "Message has invalid checksum")

            logger.info(f"sync: {repr(command)} -> {repr(data)}")
            all_data.append(data.hex())
        return all_data
