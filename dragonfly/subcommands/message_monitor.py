#!/usr/bin/python
'''
message monitoring port based on service class
'''

from __future__ import absolute_import

import json
import logging

from dripline.core import Message, Service, exceptions

logger = logging.getLogger(__name__)

__all__ = []


class Monitor(Service):
    def __init__(self, payload_only, **kwargs):
        Service.__init__(self, **kwargs)
        self._bindings.extend([[kwargs['exchange'],key] for key in kwargs['keys']])
        self._payload_only = payload_only

    def on_any_message(self, unused_channel, basic_deliver, properties, body):
        try:
            decoded = Message.from_encoded(body, properties.content_encoding)
            if self._payload_only:
                decoded = json.dumps(decoded.payload, indent=2)
        except exceptions.DriplineDecodingError as err:
            pass
        logger.log(35, # log at a level that prints even without a -v
                   '\n{} [{}]     (From App [routing_key])\n{}'.format(
                        properties.app_id,
                        basic_deliver.routing_key,
                        decoded or body,
                       )
                  )

__all__.append('MessageMonitor')
class MessageMonitor(object):
    '''
    utility for listening in on AMQP messages (does not prevent delivery but may prevent undeliverable errors if there is no other valid target)
    '''
    name = 'monitor'
    def __call__(self, kwargs):
        monitor = Monitor(
                          payload_only=kwargs.payload_only,
                          broker = kwargs.broker,
                          exchange = kwargs.exchange,
                          keys = kwargs.keys
                         )
        logger.info('starting to monitor')
        try:
            monitor.run()
        except KeyboardInterrupt:
            logger.info('received <Ctrl+c>... exiting')

    def update_parser(self, parser):
        parser.add_argument('-e',
                            '--exchange',
                            metavar='exchange name',
                            help='amqp name of the exchange to monitor',
                            default='alerts',
                           )
        parser.add_argument('-k',
                            '--keys',
                            metavar='keys',
                            help='amqp binding keys to follow',
                            default=['#'],
                            nargs='*',
                           )
        parser.add_argument('-po',
                            '--payload-only',
                            metavar='payload_only',
                            help='Print only the message.payload',
                            default=False, #value if not present
                            action='store_const',
                            const=True, #value if present w/o value
                           )
