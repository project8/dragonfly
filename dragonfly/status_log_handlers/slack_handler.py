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
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        try:
            this_home = os.path.expanduser('~')
            slack = json.loads(open(this_home+'/.project8_authentications.json').read())['slack']
            if 'dripline' in slack:
                token = slack['dripline']
            else:
                token = slack['token']
            self.slackclient = slackclient.SlackClient(token)
        except ImportError as err:
            if 'slackclient' in str(err):
                logger.warning('The slackclient package (available in pip) is required for using the slack handler')
            raise

    def emit(self, record):
        self.slackclient.api_call('chat.postMessage', channel='#p8_alerts', text=record, username='dripline', as_user='true')
