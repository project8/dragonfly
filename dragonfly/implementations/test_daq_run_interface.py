'''
A service to test interfacing with a general DAQ
'''

from __future__ import absolute_import


# standard imports
import logging

# internal imports
from dripline.core import fancy_doc
from dragonfly.implementations import DAQProvider

__all__ = []

logger = logging.getLogger(__name__)

__all__.append('TestingDAQProvider')
@fancy_doc
class TestingDAQProvider(DAQProvider):
    '''
    A class for testing a minimal DAQProvider, e.g in insectarium
    '''
    def __init__(self,
                 **kwargs):
        DAQProvider.__init__(self,**kwargs)
        self._is_running = False

    @property
    def is_running(self):
        return self._is_running

    def determine_RF_ROI(self):
        logger.debug("Imagining an ROI")

    def _do_checks(self):
        logger.debug("Thinking about pre-run checks")

    def _start_data_taking(self,directory,filename):
        self._is_running = True
        logger.debug("Visualizing data")

    def _stop_data_taking(self):
        self._is_running = False
        logger.debug("Fade to black")
