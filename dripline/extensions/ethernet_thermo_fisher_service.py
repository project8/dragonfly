import re
import socket
import threading
import time

from dripline.core import Service, ThrowReply

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

class EthernetThermoFisherService(Service):
    '''
    A fairly specific subclass of Service for connecting to ethernet-capable thermo fisher devices.
    In particular, devices must support a half-duplex serial communication with header information, variable length data-payload and a checksum.
    '''
    def __init__(self,
                 socket_timeout=10,
                 socket_info=('localhost', 1234),
                 lead_char = b'\xcc',
                 msb = b'\x00',
                 lsb = b'\x01',
                 **kwargs
                 ):
        '''
        Args:
            socket_timeout (int): number of seconds to wait for a reply from the device before timeout.
            socket_info (tuple or string): either socket.socket.connect argument tuple, or string that
                parses into one.
        '''
        Service.__init__(self, **kwargs)

        if isinstance(socket_info, str):
            logger.debug(f"Formatting socket_info: {socket_info}")
            re_str = "\([\"'](\S+)[\"'], ?(\d+)\)"
            (ip,port) = re.findall(re_str,socket_info)[0]
            socket_info = (ip,int(port))

        self.alock = threading.Lock()
        self.socket = socket.socket()
        self.socket_timeout = float(socket_timeout)
        self.socket_info = socket_info
        self.lead_char = lead_char
        self.msb = msb
        self.lsb = lsb

    def send_to_device(self, commands, **kwargs):
        '''
        Standard device access method to communicate with instrument.
        NEVER RENAME THIS METHOD!

        commands (list||None): list of command(s) to send to the instrument following (re)connection to the instrument, still must return a reply!
                             : if impossible, set as None to skip
        '''
        if isinstance(commands, str):
            commands = [commands]
        self.alock.acquire()

        try:
            data = self._send_commands(commands)
        except Exception as err:
            logger.critical(str(err))
            try:
                data = self._send_commands(commands)
                logger.critical("Query successful after ethernet connection recovered")
            except socket.error as err: # simply trying to make it possible to catch the error below
                logger.warning(f"socket.error <{err}> received, attempting reconnect")
                logger.critical("Ethernet reconnect failed, dead socket")
                raise ThrowReply('resource_error_connection', "Broken ethernet socket")
            except Exception as err: ##TODO handle all exceptions, that seems questionable
                logger.critical("Query failed after successful ethernet socket reconnect")
                raise ThrowReply('resource_error_no_response', str(err))
        finally:
            self.alock.release()
        to_return = ';'.join(data)
        logger.debug(f"should return:\n{to_return}")
        return to_return

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
            issue = True
            try:
                self.socket.close()
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, )
                self.socket.settimeout(self.socket_timeout)
                self.socket.connect(self.socket_info)
                logger.debug(f"Socket: {self.socket}")

                logger.debug(f"sending: {cmd}")
                self.socket.send(cmd)
                logger.debug("Wait for responds")
                time.sleep(0.6)
                logger.debug("Read header")
                header = self.socket.recv(5)
                nBytes = int(header[-1])
                logger.debug("Read data")
                data = self.socket.recv(nBytes)
                logger.debug("Read checksum")
                check = self.socket.recv(1)
                response = header + data + check
                issue = False
            except Exception as err:
                logger.warning(f"While socket communication we recived an error: {err}")
            finally:
                self.socket.close()
                logger.debug("Closed connection")
            if issue:
                raise ThrowReply("connection_error", "No connection to device")
            logger.info(f"Recived: {response}")
            if not self.check_checksum(response):
                raise ThrowReply("checksum_error", "Message has invalid checksum")

            logger.info(f"sync: {repr(command)} -> {repr(data)}")
            all_data.append(data.hex())
        return all_data
