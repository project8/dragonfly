'''
'''
from __future__ import absolute_import

from dripline.core import Provider, constants, fancy_doc


import logging
logger = logging.getLogger(__name__)

__all__ = ['RepeaterProvider',
          ]

@fancy_doc
class RepeaterProvider(Provider):

    def __init__(self,
                 repeat_target,
                 timeout=None,
                 **kwargs):
        '''
        repeat_target (str): name of service to send OP_SEND to
        timeout (float): time in seconds for request to timeout
        '''
        Provider.__init__(self, **kwargs)
        self._repeat_target = repeat_target
        self._timeout = timeout

    def send(self, to_send, timeout=None, ignore_retcode=False):
        if isinstance(to_send, str):
            to_send = [to_send]
        if timeout is None and self._timeout is not None:
            timeout = self._timeout
        to_send = {'values':to_send}
        logger.debug('trying to send: {}'.format(to_send))
        request_args = {'target':self._repeat_target,
                        'msgop': constants.OP_SEND,
                        'payload':to_send,
                        'timeout': timeout,
                        'ignore_retcode': ignore_retcode
                       }
        return self.provider._send_request(**request_args)
