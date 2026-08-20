from dripline.core import Entity

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('CmdEntity')
class CmdEntity(Entity):
    '''
    SCPI Entity to execute a command, instead of a get or set.
    The command is given via "cmd_str" and takes no additional arguments. 
    This can e.g. be used to auto-calibrate, set to zero or similar device commands.
    '''
    def __init__(self, cmd_str=None, **kwargs):
        '''
        Args:
            cmd_str (str): sent verbatim in the event of cmd().
        '''
        Entity.__init__(self, **kwargs)
        logger.debug(f"I get cmd_str: {cmd_str}, which is of type {type(cmd_str)}.")
        if cmd_str is None:
            raise ValueError("cmd_str is required for CmdEntity")
        self.cmd_str = cmd_str

    def cmd(self):
        logger.debug("in cmd function")
        return self.service.send_to_device([self.cmd_str])
