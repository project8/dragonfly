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
    A custom handler for sending messages to slack
    '''
    argparse_flag_str = 'slack'
    def __init__(self, broker,name=None,*args, **kwargs):
        # setting the logger listening
        logging.Handler.__init__(self, *args, **kwargs)
        self.setLevel(logging.CRITICAL)

        # setting the interface
        self.connection_to_alert = dripline.core.Service(broker=broker, exchange='alerts',keys='status_message.p8_alerts.dripline')

        #sending a welcome message
        this_channel = 'p8_alerts'
        if name is None:
            self.username = 'dripline'
        else:
            self.username = name
        severity = 'status_message.{}.{}'.format(this_channel,self.username)
        print('sending to alerts exchange with severity {} message ({})'.format(severity,'hello world'))
        self.connection_to_alert.send_status_message(severity=severity,alert='hello world')


        # this_home = os.path.expanduser('~')
        # slack = {}
        # try:
        #     slack = json.loads(open(this_home+'/.project8_authentications.json').read())['slack']
        # except:
        #     print('either unable to read ~/.project8_authentications.json or no slack field configured')
        #     #logger.warning('unable to parse authentication file')
        # token = None
        # if 'dripline' in slack:
        #     token = slack['dripline']
        # elif 'token' in slack:
        #     token = slack['token']
        # if token:
        #     self.slackclient = slackclient.SlackClient(token)
        # else:
        #     self.slackclient = None
        #     print('\nWarning! unable to find slack credentials in <~/.project8_authentications.p8>\n')

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
        print('sending to alerts exchange with severity {} message ({})'.format(severity,record.msg))

        self.connection_to_alert.send_status_message(severity=severity,alert=record.msg)
        # print('supposed to do an emit')
        # #this_channel = '#bot_integration_test'
        # if self.slackclient is not None:
        #     self.slackclient.api_call('chat.postMessage', channel=this_channel, text=record.msg, username='dripline', as_user='true')
