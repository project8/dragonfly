'''
Wrappers for the standard logging module classes
'''

from __future__ import absolute_import

import json
import os

import logging

__all__ = []

try:
    import slackclient
    __all__.append('SlackHandler')
except ImportError:
    pass

class SlackHandler(logging.Handler):
    '''
    A custom handler for sending messages to slack
    '''
    argparse_flag_str = 'slack'
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.setLevel(logging.CRITICAL)
        try:
            this_home = os.path.expanduser('~')
            try:
                slack = json.loads(open(this_home+'/.project8_authentications.json').read())['slack']
            except:
                logger.warning('unable to parse authentication file')
            if 'dripline' in slack:
                token = slack['dripline']
            else:
                token = slack['token']
            self.slackclient = slackclient.SlackClient(token)
        except ImportError as err:
            if 'slackclient' in str(err):
                logger.warning('The slackclient package (available in pip) is required for using the slack handler')
            raise
    
    def update_parser(self, parser):
        parser.add_argument('--'+self.argparse_flag_str,
                            action='store_true',
                            help='enable a status log handler to post critical messages to slack',
                           )

    def setLevel(self, level):
        '''
        for now, force the to critical...
        '''
        if level != logging.CRITICAL:
            print('warning: slack is only ever critical, setting that')
        else:
            super(SlackHandler, self).setLevel(level)

    def emit(self, record):
        print('supposed to do an emit')
        this_channel = '#p8_alerts'
        #this_channel = '#bot_integration_test'
        self.slackclient.api_call('chat.postMessage', channel=this_channel, text=record.msg, username='dripline', as_user='true')
