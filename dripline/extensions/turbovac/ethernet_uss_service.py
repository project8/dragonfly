import re
import socket
import threading

from dripline.core import Service, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('EthernetUSSService')
class EthernetUSSService(Service):
    '''
    '''
    def __init__(self,
                 socket_timeout=1.0,
                 socket_info=('localhost', 1234),
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
            print(f"Formatting socket_info: {socket_info}")
            re_str = "\([\"'](\S+)[\"'], ?(\d+)\)"
            (ip,port) = re.findall(re_str,socket_info)[0]
            socket_info = (ip,int(port))

        self.alock = threading.Lock()
        self.socket = socket.socket()
        self.socket_timeout = float(socket_timeout)
        self.socket_info = socket_info
        self.STX = b'\x02'
        self._reconnect()

    def _reconnect(self):
        '''
        Method establishing socket to ethernet instrument.
        Called by __init__ or send (on failed communication).
        '''
        # close previous connection
        # open new connection
        # check if connection was successful
        
        self.socket.close()
        self.socket = socket.socket()
        try:
            self.socket = socket.create_connection(self.socket_info, self.socket_timeout)
        except (socket.error, socket.timeout) as err:
            print(f"connection {self.socket_info} refused: {err}")
            raise Exception('resource_error_connection', f"Unable to establish ethernet socket {self.socket_info}")
        print(f"Ethernet socket {self.socket_info} established")

    def send_to_device(self, commands, **kwargs):
        '''
        Standard device access method to communicate with instrument.
        NEVER RENAME THIS METHOD!

        commands (list||None): list of command(s) to send to the instrument following (re)connection to the instrument, still must return a reply!
                             : if impossible, set as None to skip
        '''
        if not isinstance(commands, list):
            commands = [commands]
        
        self.alock.acquire()

        try:
            data = self._send_commands(commands)
        except socket.error as err:
            print(f"socket.error <{err}> received, attempting reconnect")
            self._reconnect()
            data = self._send_commands(commands)
            print("Ethernet connection reestablished")
        # exceptions.DriplineHardwareResponselessError
        except Exception as err:
            print(str(err))
            try:
                self._reconnect()
                data = self._send_commands(commands)
                print("Query successful after ethernet connection recovered")
            except socket.error: # simply trying to make it possible to catch the error below
                print("Ethernet reconnect failed, dead socket")
                raise Exception('resource_error_connection', "Broken ethernet socket")
            except Exception as err: ##TODO handle all exceptions, that seems questionable
                print("Query failed after successful ethernet socket reconnect")
                raise Exception('resource_error_no_response', str(err))
        finally:
            self.alock.release()
        to_return = b''.join(data)
        print(f"should return:\n{to_return}")
        return to_return
        
    def _send_commands(self, commands):
        '''
        Take a list of telegrams, send to instrument and receive responses, do any necessary formatting.

        commands (list||None): list of command(s) to send to the instrument following (re)connection to the instrument, still must return a reply!
                             : if impossible, set as None to skip
        '''
        all_data=[]

        for command in commands:
            if not isinstance(command, bytes):
                raise ValueError("Command is not of type bytes: {command}, {type(command)}")
            print(f"sending: {command}")
            self.socket.send(command)
            data = self._listen()
            print(f"sync: {repr(command)} -> {repr(data)}")
            all_data.append(data)
        return all_data

    def _listen(self):
        '''
        Query socket for response.
        '''
        data = b''
        length = None
        try:
            while True:
                tmp = self.socket.recv(1024)
                data += tmp
                if self.STX in data:
                    start_idx = data.find(self.STX)
                    data = data[start_idx:] # get rid of everything before the start
                if len(data)>1:             # if >1 data we have a length info
                    length = int(data[1])+2
                    if len(data) >= length:  # if we are >= LENGTH we have all we need
                        break
                if tmp == '':
                    raise Exception('resource_error_no_response', "Empty socket.recv packet")
        except socket.timeout:
            print(f"socket.timeout condition met; received:\n{repr(data)}")
            raise Exception('resource_error_no_response', "Timeout while waiting for a response from the instrument")
        print(repr(data))
        data = data[0:length]
        return data
