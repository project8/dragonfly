import threading
import os
import json
from dripline.core import Service, ThrowReply, Entity

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('StateGetEntity')
class StateGetEntity(Entity):
    def __init__(self, key, **kwargs):
        self.key = key
        Entity.__init__(self, **kwargs)
    
    def on_get(self):
        return self.service.get_state()[key]

    def on_set(self, value):
        raise ThrowReply("on_set_error", f"on_set not available for {self.name}")


__all__.append('RunStateService')
class RunStateService(Service):
    '''
    A service providing information about the current run status.
    '''
    def __init__(self,
                 state_file=None,
                 **kwargs
                 ):
        '''
        Args:
            state_file (str): File that is used to store the current run state
        '''
        Service.__init__(self, **kwargs)

        if state_file is None or not isinstance(state_file, str):
            raise ThrowReply('service_error_invalid_value', f"Invalid state file: <{state_file}>! Expect string")

        self.alock = threading.Lock()
        self.state_file
        
    def get_state(self):
        '''
        Read the state of the run from a file.
        '''
        logger.info(f"Ethernet socket {self.socket_info} established")
        self.alock.acquire()
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as open_file:
                    state = json.load(open_file)
            else:
                state = {"run_number": 1,
                         "run_comment": "Initial run",
                         "run_active": False}
        except Exception as err:
            logger.critical("")
        finally:
            self.alock.release()
        return state

    def save_state(self):
        with open(self.state_file, "w") as open_file:
            json.dump(state, open_file)
        return
