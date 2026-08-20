from dripline.core import calibrate
from dripline.implementations import FormatEntity

import logging
logger = logging.getLogger(__name__)

__all__ = []



__all__.append('AstevalFormatEntity')
class AstevalFormatEntity(FormatEntity):
    '''
    Utility Entity allowing arbitrary set and query syntax and formatting for more complicated usage cases
    No assumption about SCPI communication syntax.
    '''

    def __init__(self,
                 asteval_format_response_string="def f(response): return response",
                 **kwargs):
        '''
        Args:
            asteval_format_response_string (str): function definition to format response. Default: "def f(response): return response"
        '''
        FormatEntity.__init__(self, **kwargs)
        self.asteval_format_response_string = asteval_format_response_string # has to contain a definition "def f(response): ... return value"
        logger.debug(f'asteval_format_response_string: {repr(self.asteval_format_response_string)}')
        self.evaluator(asteval_format_response_string)

    @calibrate()
    def on_get(self):
        result = FormatEntity.on_get(self)
        raw = result["value_raw"]
        processed_result = self.evaluator(f"f('{raw}')")
        logger.debug(f"processed_result: {repr(processed_result)}")
        return processed_result
