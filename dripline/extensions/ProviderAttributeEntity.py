from dripline.core import Entity, calibrate, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []

__all__.append('ProviderAttributeEntity')
class ProviderAttributeEntity(Entity):
    '''
    Spime allowing communication with provider property.
    '''

    def __init__(self,
                 attribute_name,
                 disable_set=False,
                 **kwargs):
       Entity.__init__(self, **kwargs)
       self._attribute_name = attribute_name
       self._disable_set = disable_set

    @calibrate()
    def on_get(self):
        return getattr(self.service, self._attribute_name)

    def on_set(self, value):
        setattr(self.service, self._attribute_name, value)

