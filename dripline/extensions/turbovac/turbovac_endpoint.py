'''
A Entity is an enhanced implementation of a Dripline Endpoint with simple logging capabilities.
The Entitys defined here are more broad-ranging than a single service, obviating the need to define new Entitys for each new service or provider.

When implementing a Entity, please remember:
- All communication must be configured to return a response.  If no useful get is possible, consider a \*OPC?
- set_and_check is a generally desirable functionality
'''

from dripline.core import Entity, calibrate, ThrowReply
from .telegram.datatypes import (Data, Uint, Sint, Bin)
from .telegram.codes import (ControlBits, StatusBits, get_parameter_code, get_parameter_mode, ParameterResponse, ParameterError)
from .telegram.telegram import (Telegram, TelegramBuilder, TelegramReader)

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('TurboVACTelegramEntity')
class TurboVACTelegramEntity(Entity):
    '''
    Entity for turboVAC stuff
    '''

    def __init__(self,
                 number=None,
                 index=None,
                 **kwargs):
        '''
        Args:
            number (int): sent verbatim in the event of on_get; if None, getting of endpoint is disabled
            index (int): sent as set_str.format(value) in the event of on_set; if None, setting of endpoint is disabled
        '''
        Entity.__init__(self, **kwargs)
        self._number = number
        self._index = index

    @calibrate()
    def on_get(self):
        request_telegram = (TelegramBuilder()
                    .set_parameter_mode("read") 
                    .set_parameter_number(self._number) 
                    .set_parameter_index(self._index)
                    .set_parameter_value(0)     
                    .set_flag_bits([ControlBits.COMMAND]) 
                    .build()
                    )
        
        reply_bytes = self.service.send_to_device([bytes(request_telegram)])
        logger.debug(f'raw result is: {reply_bytes}')
        reply = TelegramBuilder().from_bytes(reply_bytes).build()
        response = TelegramReader(reply, 'reply')
        
        return response.parameter_value

    def on_set(self, value):
        request_telegram = (TelegramBuilder()
                    .set_parameter_mode("write") 
                    .set_parameter_number(self._number) 
                    .set_parameter_index(self._index)
                    .set_parameter_value(value)
                    .set_flag_bits([ControlBits.COMMAND]) 
                    .build()
                    )

        reply_bytes = self.service.send_to_device([bytes(request_telegram)])
        logger.debug(f'raw result is: {reply_bytes}')
        reply = TelegramBuilder().from_bytes(reply_bytes).build()
        response = TelegramReader(reply, 'reply')

        return response.parameter_value

__all__.append('TurboVACTelegramGetEntity')
class TurboVACTelegramGetEntity(TurboVACTelegramEntity):
    def __init__(self, **kwargs):
        TurboVACTelegramGetEntity.__init__(self, **kwargs)

    def on_set(self, value):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support set")

__all__.append('TurboVACTelegramSetEntity')
class TurboVACTelegramGetEntity(TurboVACTelegramEntity):
    def __init__(self, **kwargs):
        TurboVACTelegramGetEntity.__init__(self, **kwargs)

    def on_get(self, value):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support get")
