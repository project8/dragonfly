'''
'''

from __future__ import print_function
__all__ = []

import datetime

import dripline
from dripline.core import Gogol, constants

import logging
logger = logging.getLogger(__name__)

__all__.append('SlackService')
@dripline.core.utilities.fancy_doc
class SlackService(Gogol):
    '''
    Service which handles the display of critical messages on Slack in the p8_alerts channel
    '''
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        self.setLevel(logging.CRITICAL)
        this_home = os.path.expanduser('~')
        slack = {}
        try:
            slack = json.loads(open(this_home+'/.project8_authentications.json').read())['slack']
        except:
            print('either unable to read ~/.project8_authentications.json or no slack field configured')
            #logger.warning('unable to parse authentication file')
        token = None
        if 'dripline' in slack:
            token = slack['dripline']
        elif 'token' in slack:
            token = slack['token']
        if token:
            self.slackclient = slackclient.SlackClient(token)
        else:
            self.slackclient = None
            print('\nWarning! unable to find slack credentials in <~/.project8_authentications.p8>\n')
