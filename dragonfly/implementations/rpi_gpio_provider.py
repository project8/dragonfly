from __future__ import absolute_import

try:
    import RPi.GPIO as GPIO
except ImportError:
    pass

from dripline.core import Provider, fancy_doc
from . import GPIOSpime

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('RPiGPIOProvider')
@fancy_doc
class RPiGPIOProvider(Provider):
    '''
    A Provider class intended for control of GPIO pins on Raspberry Pi.

    This class is intended to be used with a set of GPIOSpime endpoints, use of
    get_on_set is recommended.
    '''
    def __init__(self,
                 **kwargs
                 ):
        if not 'GPIO' in globals():
            raise ImportError('RPi.GPIO not found, required for RPiGPIOProvider class')
        Provider.__init__(self, **kwargs)

        # configure pin numbering (alternative is GPIO.BCM)
        GPIO.setmode(GPIO.BOARD)

        # ignore any previous pin configurations
        GPIO.setwarnings(False)


    def configure_pins(self, *args, **kwargs):
        '''
        After endpoints have been declared, set GPIO mode of pins
        '''
        # initialize pins
        for child in self.endpoints:
            logger.debug('configuring {}'.format(child))
            if not isinstance(self.endpoints[child], GPIOSpime):
                continue
            if not self.endpoints[child].inpin and not self.endpoints[child].outpin:
                logger.critical('Cannot configure pins for GPIOSpime {}'.format(self.endpoints[child]))
                continue
            if self.endpoints[child].inpin:
                for pin in self.endpoints[child].inpin:
                    GPIO.setup(pin, GPIO.IN)
            if self.endpoints[child].outpin:
                for pin in self.endpoints[child].outpin:
                    GPIO.setup(pin, GPIO.OUT)
