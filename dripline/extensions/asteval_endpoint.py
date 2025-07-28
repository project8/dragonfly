import asteval # used for FormatEntity
import re # used for FormatEntity

from dripline.core import calibrate, ThrowReply
from dripline.implementations import FormatEntity
from dripline.core import Entity

import logging
logger = logging.getLogger(__name__)

__all__ = []



__all__.append('FormatEntityAsteval')
class FormatEntityAsteval(FormatEntity):
    '''
    Utility Entity allowing arbitrary set and query syntax and formatting for more complicated usage cases
    No assumption about SCPI communication syntax.
    '''

    def __init__(self,
                 asteval_get_string="def f(response): return response",
                 **kwargs):
        '''
        Args:
            get_str (str): sent verbatim in the event of on_get; if None, getting of endpoint is disabled
            get_reply_float (bool): apply special formatting to get return
            set_str (str): sent as set_str.format(value) in the event of on_set; if None, setting of endpoint is disabled
            set_value_lowercase (bool): default option to map all string set value to .lower()
                **WARNING**: never set to False if using a set_value_map dict
            set_value_map (str||dict): inverse of calibration to map raw set value to value sent; either a dictionary or an asteval-interpretable string
            extract_raw_regex (str): regular expression search pattern applied to get return. Must be constructed with an extraction group keyed with the name "value_raw" (ie r'(?P<value_raw>)' ) 
            asteval_get_string (str): function definition to format response. Default: "def f(response): return response"
        '''
        FormatEntity.__init__(self, **kwargs)
        self.asteval_get_string = asteval_get_string # has to contain a definition "def f(response): ... return value"
        logger.debug(f'asteval_get_string: {repr(self.asteval_get_string)}')
        self.evaluator(asteval_get_string)

    @calibrate()
    def on_get(self):
        result =FormatEntity.on_get(self)
        raw = result["value_raw"]
        processed_result = self.evaluator(f"f('{raw}')")
        logger.debug(f"processed_result: {repr(processed_result)}")
        return processed_result



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
        self.cmd_str = cmd_str

    def cmd(self):
        logger.debug("Command function was successfully called")
        if self.cmd_str is None:
            raise ThrowReply('service_error', f"endpoint '{self.name}' does not support cmd")
        return self.service.send_to_device([self.cmd_str])
