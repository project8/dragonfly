'''
A Provider class for interfacing with the Lockin amplifier
'''

from __future__ import absolute_import

from dripline.core import fancy_doc
from dragonfly.implementations import PrologixProvider

import logging
logger = logging.getLogger(__name__)

__all__ = ['LockinProvider']

@fancy_doc
class LockinProvider(PrologixProvider):

    def __init__(self, **kwargs):
        PrologixProvider.__init__(self, **kwargs)

    def grab_data(self, key):
        '''
        Returns available data curves

        key (int): key of curve to grab
        '''
        pts = int(self.send(["LEN"]))
        logger.info("expect {} pt data curves".format(pts))
        cbd = int(self.send(["CBD"]))
        logger.info("mask of available data curves is {}".format(cbd))
        if not cbd & 0b00010000:
            raise ValueError("No floating point data available, reconfigure CBD")
        status = self.send(["M"])
        status = map(int, status.split(','))
        logger.info("{} curve(s) available, {} points per curve".format(status[1], status[3]))
        if status[1] != 1:
            raise ValueError("No curve available")
        if status[3] != pts:
            raise ValueError("Unexpected number of data points")
        if not isinstance(key, int):
            key = key.lower()
            if key == "x": key = 0
            elif key == "y": key = 1
            elif key == "mag": key = 2
            elif key == "phase": key = 3
            elif key == "adc": key = 5
            else:
                raise ValueError("Invalid string key.")
        if not (1<<key) & cbd:
            raise ValueError("Curve {} not available, reconfigure CBD".format(key))
        command = ["++eot_enable 1\rDC. {};ID".format(key),
                   "++eot_enable 0\r++eot_enable"]
        result = self.send(command)
        delimit = "\r\n*"
        if pts-1 != result.count(delimit):
            raise ValueError("Missing data points")
        result = result.split(";")[0]
        return result.replace(delimit, ";")
