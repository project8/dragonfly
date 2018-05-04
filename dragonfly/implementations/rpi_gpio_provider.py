from __future__ import absolute_import

try:
    import RPi.GPIO as GPIO
    from Adafruit_MAX31856 import MAX31856
except ImportError:
    pass

from dripline.core import Provider, fancy_doc
from . import GPIOSpime, GPIOPUDSpime

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('RPiGPIOProvider')
@fancy_doc
class RPiGPIOProvider(Provider):
    '''
    A Provider class intended for generic control of GPIO pins on Raspberry Pi.
    Custom configure methods provided for different applications intended for
    use as setup_calls.

    This class is intended to be used with a set of GPIO-related Spime endpoints.
    '''
    def __init__(self,
                 pinmap=10,
                 **kwargs
                 ):
        '''
        pinmap (int): select GPIO.BOARD (10) or GPIO.BCM (11) mapping of pins
        '''
        if not 'GPIO' in globals():
            raise ImportError('RPi.GPIO not found, required for RPiGPIOProvider class')
        Provider.__init__(self, **kwargs)
        GPIO.setmode(pinmap)
        self.GPIO = GPIO


    def configure_pins(self, *args, **kwargs):
        '''
        Configure basic input/output GPIO pins.
        '''
        # ignore any previous pin configurations
        GPIO.setwarnings(False)

        # initialize pins
        for child in self.endpoints:
            if not isinstance(self.endpoints[child], GPIOSpime):
                logger.debug('cannot configure {}'.format(child))
                continue
            logger.debug('configuring {}'.format(child))
            if self.endpoints[child]._inpin:
                for pin in self.endpoints[child]._inpin:
                    GPIO.setup(pin, GPIO.IN)
            if self.endpoints[child]._outpin:
                for pin in self.endpoints[child]._outpin:
                    GPIO.setup(pin, GPIO.OUT)

    def configure_pud(self, *args, **kwargs):
        '''
        Configure GPIO pins with PUD event
        '''
        for child in self.endpoints:
            if not isinstance(self.endpoints[child], GPIOPUDSpime):
                logger.debug('cannot configure {}'.format(child))
                continue
            logger.debug('configuring {}'.format(child))
            GPIO.setup(self.endpoints[child]._pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(self.endpoints[child]._pin, GPIO.RISING, callback=self.endpoints[child]._countPulse)
            self.endpoints[child]._reset()

    def configure_max31856(self, *args, **kwargs):
        '''
        Configure max31856 with SPI pin assignments, defaults are:
            cs = 8
            do = 9
            di = 10
            clk = 11
        '''
        if len(kwargs) != 4:
            logger.warning('Badly formatted args for configure_max31856: <{}>!'.format(kwargs))
            raise ValueError

        self.max31856 = MAX31856(software_spi=kwargs)
