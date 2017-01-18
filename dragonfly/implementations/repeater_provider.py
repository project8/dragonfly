'''
'''
from __future__ import absolute_import

import sys

from dripline.core import Provider, message, constants, exception_map


import logging
logger = logging.getLogger(__name__)

__all__ = ['RepeaterProvider',
          ]

class RepeaterProvider(Provider):

    def __init__(self,
                 repeat_target,
                 broker,
                 timeout=10,
                 **kwargs):
        Provider.__init__(self, **kwargs)
        self._timeout = timeout
        self._repeat_target = repeat_target
        self._broker_info = broker

    def send_request(self, target, request):
        result = self.service.send_request(self._repeat_target, request, timeout=self._timeout)
        if result.retcode != 0:
            msg = ''
            if 'ret_msg' in result.payload:
                msg = result.payload['ret_msg']
            # Exception 201 means wolfburn is having connection issues and isn't spamming errors.
            if result.retcode == 201:
                raise exception_map[result.retcode](msg)
            else:
                logger.critical("{} returned from {} with message {}. {} service crashing.".\
                    format(exception_map[result.retcode],self._repeat_target,repr(msg),self.name))
                sys.exit()
        return result.payload

    def send(self, to_send):
        if isinstance(to_send, str):
            to_send = [to_send]
        to_send = {'values':to_send}
        logger.debug('trying to send: {}'.format(to_send))
        request = message.RequestMessage(msgop=constants.OP_SEND,
                                         payload=to_send,
                                        )
        return self.send_request(self._repeat_target, request)['values']
