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
import datetime
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
        logger.debug(self.service.control_bits)
        request_telegram = (TelegramBuilder()
                    .set_parameter_mode("read") 
                    .set_parameter_number(self._number) 
                    .set_parameter_index(self._index)
                    .set_parameter_value(0)     
                    .set_flag_bits(self.service.control_bits) 
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
                    .set_flag_bits(self.service.control_bits) 
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
        TurboVACTelegramEntity.__init__(self, **kwargs)

    def on_set(self, value):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support set")

__all__.append('TurboVACTelegramSetEntity')
class TurboVACTelegramSetEntity(TurboVACTelegramEntity):
    def __init__(self, **kwargs):
        TurboVACTelegramEntity.__init__(self, **kwargs)

    def on_get(self, value):
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support get")

__all__.append('TurboVACTelegramStateEntity')
class TurboVACTelegramStateEntity(Entity):
    def __init__(self,
                 checkin_interval=None,
                 **kwargs):
        '''
        Args:
            number (int): sent verbatim in the event of on_get; if None, getting of endpoint is disabled
            index (int): sent as set_str.format(value) in the event of on_set; if None, setting of endpoint is disabled
        '''
        Entity.__init__(self, **kwargs)
        self.checkin_interval = checkin_interval
        self._checkin_action_id = None
        self._state = []

    def checkin(self): 
        state_telegram = (TelegramBuilder()
                          .set_flag_bits(self.service.control_bits) 
                          .build()
                          )
        
        reply_bytes = self.service.send_to_device([bytes(state_telegram)])
        logger.debug(f'raw result is: {reply_bytes}')
        reply = TelegramBuilder().from_bytes(reply_bytes).build()
        response = TelegramReader(reply, 'reply')
        
        return response.parameter_value


    def control_enable(self):
        if self._log_action_id is not None:
            self.service.unschedule(self._log_action_id)
        if self.checkin_interval:
            logger.info(f'should enable control every {self.checkin_interval}')
            if not ControlBits.COMMAND in self.service.control_bits:
                self.service.control_bits.append(ControlBits.COMMAND)
            self._log_action_id = self.service.schedule(self.checkin, datetime.timedelta(seconds=self.checkin_interval), datetime.datetime.now() + self.service.execution_buffer*3)
        else:
            raise ValueError('unable to enable control when checkin_interval evaluates false')
        logger.debug(f'log action id is {self._log_action_id}')

    def control_disable(self):
        if ControlBits.COMMAND in self.service.control_bits:
            self.service.control_bits.remove(ControlBits.COMMAND)
        if self._log_action_id is not None:
            self.service.unschedule(self._log_action_id)
        self._log_action_id = None

    def start_pump(self):
        if not ControlBits.ON in self.service.control_bits:
            self.service.control_bits.append(ControlBits.ON)
        if not ControlBits.COMMAND in self.service.control_bits:
            logger.info(f'You try to turn on the pump but did not enable control')

    def stop_pump(self):
        if ControlBits.ON in self.service.control_bits:
            self.service.control_bits.remove(ControlBits.ON)
