#!/usr/bin/python
'''
Utility app for posting messages to slack
'''

from __future__ import absolute_import

import json
import os
import re

import slackclient

import dripline
from dripline.core import Gogol

import logging
logger=logging.getLogger(__name__)

class SlackInterface(Gogol):
    '''
    A generic service that will repeat AMQP messages to messages on slack.
    '''
    def __init__(self, **kwargs):
        # listen to status_message alerts channel
        kwargs.update({'exchange':'alerts','keys':['status_message.#.#']})
        # kwargs.update({'exchange':'alerts','keys':['#']})
        Gogol.__init__(self, **kwargs)

        this_home = os.path.expanduser('~')
        slack = {}
        # slack = json.loads(open(this_home+'/.project8_authentications.json').read())['slack']
        config_file = json.loads(open(this_home+'/.project8_authentications_project8.json').read())
        if 'slack' in config_file:
            slack = config_file['slack']
        else:
            raise dripline.core.exceptions.DriplineValueError('Warning! unable to find slack credentials in <~/.project8_authentications.p8>')
        print(slack)
        token = None
        if 'dripline' in slack:
            token = slack['dripline']
        elif 'token' in slack:
            token = slack['token']
        if token:
            self.slackclient = slackclient.SlackClient(token)
        else:
            self.slackclient = None
            raise dripline.core.exceptions.DriplineValueError('Warning! unable to find slack token in <~/.project8_authentications.p8>')

        # this_home = os.path.expanduser('~')
        # _tokens = json.loads(open(this_home+'/.project8_authentications.json').read())['slack']
        # self._slackclients = {}
        # for bot,token in _tokens.items():
        #     self._slackclients[bot] = slackclient.SlackClient(token)

    def on_alert_message(self, channel, method, properties, message):
        # parse the routing key
        logger.debug('parsing routing key')
        # print(message)
        key_parser = r'status_message.(?P<channel>[\w]+).(?P<from>[\w]+)'
        routing_info = re.search(key_parser, method.routing_key).groupdict()
        #
        # parse the message
        msg = dripline.core.Message.from_encoded(message, properties.content_encoding)
        # print(msg)
        logger.debug('selecting client')
        as_user = 'false'
        #???????
        # if routing_info['from'] in self._slackclients:
        #     this_client = self._slackclients[routing_info['from']]
        #     as_user = 'true'
        # elif 'token' in self._slackclients:
        #     this_client = self._slackclients['token']
        # else:
        #     this_client = self._slackclients['dripline']
        # ????????
        logger.debug('posting message')
        api_out = self.slackclient.api_call('chat.postMessage',
                                    #    channel='#'+routing_info['channel'],
                                       channel='#slack_test',
                                       text=str(msg.payload),
                                       username=routing_info['from'],
                                       as_user=as_user,
                                      )
        logger.debug('api call returned:{}'.format(api_out))
