from __future__ import absolute_import

try:
    import RPi.GPIO as GPIO
    from Adafruit_MAX31856 import MAX31856
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
    A Provider class intended for generic control of GPIO pins on Raspberry Pi.
    Custom configure methods provided for different applications.

    This class is intended to be used with a set of GPIOSpime endpoints, use of
    get_on_set is recommended.
    '''
    def __init__(self,
                 **kwargs
                 ):
        if not 'GPIO' in globals():
            raise ImportError('RPi.GPIO not found, required for RPiGPIOProvider class')
        Provider.__init__(self, **kwargs)


    def configure_pins(self, *args, **kwargs):
        '''
        After endpoints have been declared, set GPIO mode of pins via setup_calls
        '''

        # configure pin numbering (alternative is GPIO.BCM)
        GPIO.setmode(GPIO.BOARD)
        # ignore any previous pin configurations
        GPIO.setwarnings(False)

        # initialize pins
        for child in self.endpoints:
            logger.debug('configuring {}'.format(child))
            if not isinstance(self.endpoints[child], GPIOSpime):
                continue
            if not self.endpoints[child]._inpin and not self.endpoints[child]._outpin:
                logger.critical('Cannot configure pins for GPIOSpime {}'.format(self.endpoints[child]))
                continue
            if self.endpoints[child]._inpin:
                for pin in self.endpoints[child]._inpin:
                    GPIO.setup(pin, GPIO.IN)
            if self.endpoints[child]._outpin:
                for pin in self.endpoints[child]._outpin:
                    GPIO.setup(pin, GPIO.OUT)

    def configure_max31856(self, *args, **kwargs):
        '''
        Configure max31856 with SPI pin assignments, defaults are:
            cs = 8
            do = 9
            di = 10
            clk = 11
        '''
        if not 'MAX31856' in globals():
            raise ImportError('MAX31856 not found, required for reading temperature with RPiGPIOProvider class')
        if len(kwargs) != 4:
            logger.warning('Badly formatted args for configure_max31856: <{}>!')
            raise ValueError

        self.max31856 = MAX31856(software_spi=kwargs)
