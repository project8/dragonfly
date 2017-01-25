'''
Wrappers for the standard logging module classes
'''

from __future__ import absolute_import

import json
import os

import logging
import dripline

__all__ = []
__all__.append('AMQPHandler')


class AMQPHandler(logging.Handler):
    '''
    A custom handler for sending messages to AMQP server
    '''
    argparse_flag_str = 'amqp'
    def __init__(self, broker,name=None,*args, **kwargs):
        # setting the logger listening
        logging.Handler.__init__(self, *args, **kwargs)
        self.setLevel(logging.CRITICAL)

        # setting the interface
        self.connection_to_alert = dripline.core.Service(broker=broker, exchange='alerts',keys='status_message.#.#')

        #sending a welcome message
        this_channel = 'p8_alerts'
        if name is None:
            self.username = 'dripline'
        else:
            self.username = name

    def update_parser(self, parser):
        parser.add_argument('--'+self.argparse_flag_str,
                            action='store_false',
                            help='disable the status log handler to post critical messages to slack',
                           )

    def setLevel(self, level):
        '''
        for now, force the to critical...
        '''
        if level != logging.CRITICAL:
            print('warning: slack is only ever critical, setting that')
        else:
            super(AMQPHandler, self).setLevel(level)


    def emit(self, record):
        this_channel = 'p8_alerts'
        severity = 'status_message.{}.{}'.format(this_channel,self.username)

        self.connection_to_alert.send_status_message(severity=severity,alert=record.msg)
