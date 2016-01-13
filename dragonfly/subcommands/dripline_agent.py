#!/usr/bin/python
""" dripline_agent
Do simple stuff like gets and sets.
"""
from __future__ import absolute_import

import types
import uuid

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
                             'broadcast.ping'
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
            if a_reply.return_msg:
                logger.log(25, 'return message: {}'.format(a_reply.return_msg))
        return reply[0].payload
    
    @staticmethod
    def cast_arg(value):
        '''
        convert reasonable string arguments from the CLI to python types
        '''
        temp_val = value
        try:
            temp_val = float(value)
            temp_val = int(value)
        except ValueError:
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

class Get(GenericAgent):
    '''
    return the value of an endpoint or a property of an endpoint if specified
    '''
    name = 'get'

    def __call__(self, args):
        result = self._call(args)
        these_args = args
        if args.pretty_print:
            if not 'value_cal' in result:
                logger.warning('no value cal present, unable to pretty-print')
            else:
                print('\n{}\n'.format(result['value_cal']))

    def update_parser(self, parser):
        super(Get, self).update_parser(parser)
        parser.add_argument('--pretty-print',
                            action='store_true',
                            help='attempt to print value_cal in a manor easily read by humans (and pasted into elogs)',
                           )


class Set(GenericAgent):
    '''
    set the value of an endpoint, or a property of an endpoint if specified
    '''
    name = 'set'


class Config(GenericAgent): 
    '''
    <deprecated> query or set the value of a property of an endpoint
    '''
    name = 'config'
    def __call__(self, kwargs):
        logger.warning("OP_CONFG is going to be deprecated, consider other usage")
        super(Config, self).__call__(kwargs)


class Run(GenericAgent):
    '''
    send an OP_RUN, further details are endpoint specific
    '''
    name = 'run'


class Cmd(GenericAgent):
    '''
    have an endpoint execute an internal function
    '''
    name = 'cmd'

class Send(GenericAgent):
    '''
    have an endpoint (which is probably also a provider) execute a send
    '''
    name = 'send'


__all__ += ['Get', 'Set', 'Config', 'Run', 'Cmd', 'Send']
