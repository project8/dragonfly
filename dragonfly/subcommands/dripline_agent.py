#!/usr/bin/python
""" dripline_agent
Do simple stuff like gets and sets.
"""
from __future__ import absolute_import

import types
import uuid
import ast

from dripline.core import message, constants, Service, Message, exceptions

__all__ = []
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GenericAgent(object):
    name = None

    def __call__(self, args):
        self._call(args)

    def _call(self, args):
        '''
        main action of __call__
        '''
        logger.debug('in agent, got args:\n{}'.format(args))
        msgop = getattr(constants, 'OP_'+self.name.upper())
        conn = Service(broker = args.broker,
                       exchange = 'requests',
                       keys = '#'
                      )

        values = []
        payload = {}
        for val in args.values:
            temp_val = self.cast_arg(val)
            if isinstance(temp_val, types.StringType):
                if len(temp_val.split('=')) > 1:
                    value = self.cast_arg('='.join(temp_val.split('=')[1:]))
                    payload.update({temp_val.split('=')[0]:value})
                else:
                    values.append(temp_val)

            else:
                values.append(temp_val)

        payload.update({'values':values})
        broadcast_targets = ['broadcast.lock',
                             'broadcast.unlock',
                             'broadcast.ping',
                             'broadcast.set_condition'
                            ]
        if args.target.startswith('broadcast') and args.target not in broadcast_targets:
            # this try block is for python 2/3 compliance
            try:
                input = raw_input
            except NameError:
                pass
            confirm = input('You are about to send a broadcast to all services, are you sure?[y/n]\n')
            if not confirm.lower().startswith('y'):
                logger.info('exiting without sending request')
                return

        logger.debug('payload will be: {}'.format(payload))
        request = message.RequestMessage(msgop=msgop, payload=payload, lockout_key=args.lockout_key)
        try:
            reply = conn.send_request(args.target, request, timeout=args.timeout, multi_reply=args.target.startswith('broadcast'))
        except exceptions.DriplineAMQPConnectionError as dripline_error:
            logger.warning('{}; did you pass in a broker with "-b" or "--broker"?'.format(dripline_error.message))
            return
        except exceptions.DriplineException as dripline_error:
            logger.warning(dripline_error.message)
            return
        if not isinstance(reply, list):
            reply = [reply]
        logger.info('response:\n{}'.format(reply))
        print_prefix = '->'.join([args.target]+args.values)
        color = ''
        for a_reply in reply:
            if not a_reply.retcode == 0:
                color = '\033[91m'
            print('{color}{}(ret:{}): [{}]-> {}\033[0m'.format(print_prefix, a_reply.retcode, a_reply.sender_info['service_name'], a_reply.payload, color=color))
            if a_reply.return_msg and not a_reply.retcode == 0:
                logger.log(25, 'return message: {}'.format(a_reply.return_msg))
        if args.pretty_print:
            if 'value_cal' not in reply[0].payload:
                logger.warning('no value cal present, unable to pretty-print')
            else:
                print('\n{}\n'.format(reply[0].payload['value_cal']))


    @staticmethod
    def cast_arg(value):
        '''
        convert reasonable string arguments from the CLI to python types
        '''
        temp_val = value
        try:
            temp_val = ast.literal_eval(value)
        except (ValueError,SyntaxError):
            if isinstance(temp_val, types.StringType):
                try:
                    if value.lower() == 'true':
                        temp_val = True
                    elif value.lower() == 'false':
                        temp_val = False
                    elif value.lower() in ['none', 'nil', 'null']:
                        temp_val = None
                except ValueError:
                    pass
        return temp_val

    def update_parser(self, parser):
        parser.add_argument('target')
        parser.add_argument('values', nargs='*')
        parser.add_argument('--timeout',
                            default=10,
                            type=float,
                            help='maximum time, in seconds, to wait for a Reply',
                           )
        parser.add_argument('--lockout-key',
                            metavar='lockout_key',
                            default=None,
                            type=str,
                            help='string to provide in the RequestMessage.lockout_key, for locking endpoints or using locked endpoints',
                           )
        parser.add_argument('--pretty-print',
                            action='store_true',
                            help='attempt to print value_cal in a manner easily read by humans (and pasted into elogs)',
                           )

__all__.append("Get")
class Get(GenericAgent):
    '''
    return the value of an endpoint or a property of an endpoint if specified
    '''
    name = 'get'


__all__.append("Set")
class Set(GenericAgent):
    '''
    set the value of an endpoint, or a property of an endpoint if specified
    '''
    name = 'set'


__all__.append("Run")
class Run(GenericAgent):
    '''
    send an OP_RUN, further details are endpoint specific
    '''
    name = 'run'


__all__.append('Cmd')
class Cmd(GenericAgent):
    '''
    have an endpoint execute an internal function
    '''
    name = 'cmd'


__all__.append("Send")
class Send(GenericAgent):
    '''
    have an endpoint (which is probably also a provider) execute a send
    '''
    name = 'send'
