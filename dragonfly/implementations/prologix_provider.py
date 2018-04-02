'''
<this should say something useful>
'''

from __future__ import absolute_import

import sys

from .repeater_provider import RepeaterProvider
from dripline.core import exceptions, fancy_doc

import logging
logger = logging.getLogger(__name__)

__all__ = ['PrologixProvider']


@fancy_doc
class PrologixProvider(RepeaterProvider):
    '''
    A Provider class intended for GPIB devices that implement the full
    IEEE 488.2 (488.1 or 488 need to use some other class).
    It expects to have a set of *Spime endpoints which return SCPI commands.
    '''
    def __init__(self,
                 addr,
                 response_terminator=None,
                 **kwargs):
        '''
        addr (int): GPIB address of instrument
        response_terminator (str): optional terminator to check responses for and strip off
        '''
        RepeaterProvider.__init__(self, **kwargs)
        self.addr = addr
        self.response_terminator = response_terminator

    def _check_status(self):
        raw = self.provider.send('*ESR?', from_spime=self)
        if raw:
            data = int(raw)
        else:
            return "No response"
        status = ""
        if data & 0b00000100:
            ";".join([status, "query error"])
        if data & 0b00001000:
            ";".join([status, "device error"])
        if data & 0b00010000:
            ";".join([status, "execution error"])
        if data & 0b00100000:
            ";".join([status, "command error"])
        return status

    def send(self, cmd, timeout=None):
        to_send = ['++addr {}\r++addr'.format(self.addr)] + cmd
        try:
            #FIXME: super(PrologixProvider,self).send is returning PrologixProvider.send, not RepeaterProvider.send?
            result = RepeaterProvider.send(self, to_send, timeout)['values']
        # DriplineHardwareConnectionError means prologix has gone silent and isn't spamming errors.
        except exceptions.DriplineHardwareConnectionError as err:
            raise exceptions.DriplineHardwareConnectionError(err)
        except exceptions.DriplineException as err:
            logger.critical("{} returned from {} with message '{}' and payload '{}'. {} service crashing.".\
                format(type(err),self._repeat_target,err.msg,err.result,self.name))
            sys.exit()
        logger.debug('raw result:\n{}'.format(result))
        addr, result = result[0].split(";", 1)
        if self.response_terminator is not None:
            if addr.endswith(self.response_terminator):
                addr = addr[:-len(self.response_terminator)]
                logger.debug("GPIB address check trimmed to {}".format(addr))
            if result.endswith(self.response_terminator):
                result = result[:-len(self.response_terminator)]
                logger.debug("result trimmed to {}".format(result))
        if int(addr) != self.addr:
            raise exceptions.DriplineValueError("Unable to set GPIB address at prologix")
        logger.debug("instrument got back: {}".format(result))
        return result
