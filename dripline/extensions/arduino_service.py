import re
import socket
import threading

from dripline.core import Service

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append('EthernetArduinoService')

class EthernetArduinoService(Service):
    def __init__(self,
                 socket_info,
                 socket_timeout=10,
                 **kwargs
                 ):
    
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
 

    def send_to_device(self, commands, **kwargs):
        
        if isinstance(commands, str):
            commands = [commands]
        
        self.alock.acquire()
        data = []
        try:
            data = self._send_commands(commands)
        except Exception as err:
            logger.critical(str(err))
        finally:
            self.alock.release()
        to_return = ';'.join(data)
        logger.debug(f"should return:\n{to_return}")
        return to_return


    def _send_commands(self, commands):
        all_data=[]

        for command in commands:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.socket_timeout)
                self.socket.connect(self.socket_info)
                self.socket.sendall(bytes(command, encoding="utf-8"))
                data = self.socket.recv(1024)
                data = data.rstrip(b'\x00\n').decode("utf-8")
            except Exception as err:
                logger.warning(f"While socket communication we received an error: {err}")
            finally:
                self.socket.close()
          
            logger.info(f"Received: {data}")

            all_data.append(data)
        
        return all_data