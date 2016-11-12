#!/usr/bin/python
'''
Utility app for posting messages to slack
'''

from __future__ import absolute_import

import json
import os
import re
from datetime import datetime, timedelta

import slackclient

import dripline
from dripline.core import Gogol

import logging
logger=logging.getLogger(__name__)

class SlackInterface(Gogol):
    '''
    A generic service that will repeat AMQP messages to messages on slack.
    '''
    def __init__(self,
                 prime_speakers = None,
                 speaking_time = 60,
                 time_between_warnings=600,
                 number_sentence_per_speaking_time = 30,
                 **kwargs):
        '''
        prime_speakers: define which users are allowed to speak as much as they want and we are not allowed to stop them from it
        '''
        # listen to status_message alerts channel
        kwargs.update({'exchange':'alerts','keys':['status_message.#.#']})
        Gogol.__init__(self, **kwargs)

        # get the authentification file and look for a slack field
        this_home = os.path.expanduser('~')
        slack = {}
        config_file = json.loads(open(this_home+'/.project8_authentications_project8.json').read())
        if 'slack' in config_file:
            slack = config_file['slack']
        else:
            raise dripline.core.exceptions.DriplineValueError('Warning! unable to find slack credentials in <~/.project8_authentications.p8>')

        # grab the token used for authentification to slack
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

        # Keep track of the frequency of emission of the services
        self.history = {}
        self._prime_speakers = prime_speakers
        self._speaking_time = speaking_time
        self._time_between_warnings = time_between_warnings
        self._nspst = number_sentence_per_speaking_time


    def on_alert_message(self, channel, method, properties, message):
        # parse the routing key
        logger.debug('parsing routing key')
        key_parser = r'status_message.(?P<channel>[\w]+).(?P<from>[\w]+)'
        routing_info = re.search(key_parser, method.routing_key).groupdict()
        # parse the message
        msg = dripline.core.Message.from_encoded(message, properties.content_encoding)

        self._update_history(routing_info['from'])
        username = routing_info['from']
        if self._is_allowed_to_talk(routing_info['from']):
            logger.debug('posting message: {}'.format(str(msg.payload)))
            api_out = self.slackclient.api_call('chat.postMessage',
                                        #    channel='#'+routing_info['channel'],
                                           channel='#slack_test',
                                           text=str(msg.payload),
                                           username=username,
                                        #    username='toto',
                                           as_user='false', #false allows to send messages with unregistred username (like toto) in the channel
                                          )
            logger.debug('api call returned:{}'.format(api_out))
            self.history[username]['last_talks'].append(datetime.now())
        else:
            if self.history[username]['last_warning'] is 'never' or (datetime.now()-self.history[username]['last_warning']).seconds > self._time_between_warnings:
                logger.debug('sending warning')
                message = '{} spoke x times over the last x s: I muted it!'.format(routing_info['from'])
                api_out = self.slackclient.api_call('chat.postMessage',
                                                #    channel='#'+routing_info['channel'],
                                                   channel='#slack_test',
                                                   text=message,
                                                   username='Security',
                                                #    username='toto',
                                                   as_user='false', #false allows to send messages with unregistred username (like toto) in the channel
                                                  )
                logger.debug('api call returned:{}'.format(api_out))
                self.history[username]['last_warning'] = datetime.now()
            else:
                logger.debug('{} was warned recently: not sending warning'.format(routing_info['from']))

    def _update_history(self,username):
        if username not in self.history:
            self.history.update({username:{}})
            self.history[username].update({'last_talks':[]})
            self.history[username].update({'last_warning':'never'})
        now = datetime.now()
        for time in self.history[username]['last_talks']:
            deltat = now - time
            if deltat.seconds > self._speaking_time:
                self.history[username].remove(time)
        print(self.history)

    def _is_allowed_to_talk(self,username):

        # return true for allowed talk
        # return false for unallowed
        if username in self._prime_speakers:
            is_allowed = True
        else:
            # print(self.history[username]['last_talks'].size())
            if self.history[username]['last_talks'] == [] or len(self.history[username]['last_talks']) < self._nspst:
                is_allowed = True

            else:
                logger.info('{} user not allowed to talk: talk {} over the last {} s'.format(username, len(self.history[username]['last_talks']), self._speaking_time))
                is_allowed = False

        return is_allowed
