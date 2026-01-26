from dripline.core import Entity, calibrate, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append("ArduinoGetEntity")

class ArduinoGetEntity(Entity):
    def __init__(self, 
                 get_str=None,
                 **kwargs):

        Entity.__init__(self, **kwargs)
        self.get_str = get_str

    @calibrate()
    def on_get(self):
        return self.service.send_to_device([self.get_str])

    def on_set(self, value):       
        raise ThrowReply('message_error_invalid_method', f"endpoint '{self.name}' does not support set")