'''
<this should say something useful>
'''

from __future__ import absolute_import

from dripline.core import Provider

import logging
logger = logging.getLogger(__name__)

__all__ = ['PrologixProvider']


class PrologixProvider(Provider):
    '''
    A Provider class intended for GPIB devices that implement the full
    IEEE 488.2 (488.1 or 488 need to use some other class).

    It expects to have a set of Simple*Spime endpoints which return SCPI commands.
    The _cmd_term attribute is appended to those commands before being passed up to
    the higher level provider which actually maintains a connection (eg RepeaterProvider).
    '''
    def __init__(self, name, addr, **kwargs):
        Provider.__init__(self, name=name, **kwargs)
        self.addr = addr
        self.status = 0
        self.provider = None
        self._cmd_term = '\n'

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

    def send(self, cmd):
        if isinstance(cmd, str):
            cmd = [cmd]
        to_send = ['++addr {}\r++addr'.format(self.addr)] + cmd
        result = self.provider.send(to_send)
        logger.debug('raw result:\n{}'.format(result))
        addr, result = result[0].split(";", 1)
        if int(addr) != self.addr:
            raise DriplineValueError("Unable to set GPIB address at prologix")
        logger.debug("instr got back: {}".format(result))
        return result
