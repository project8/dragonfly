#!/usr/bin/python
""" dripline_agent
Do simple stuff like gets and sets.
"""
from __future__ import absolute_import

import types
import uuid

from dripline.core import message, constants, DriplineParser, Service, Message, exceptions

__all__ = []
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def verb_list():
    """
    A list of acceptable verb arguments.
    """
    verbs = [v[3:].lower() for v in dir(constants) if v.startswith('OP_')]
    return verbs

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

class GenericAgent(object):
    name = None

    def __call__(self, kwargs):
        try:
            agent_action(request_verb=self.name, args=kwargs)
        except KeyboardInterrupt:
            logger.warning('aborting due to <Ctrl+c>')

    def update_parser(self, parser):
        parser.add_argument('target')
        parser.add_argument('values', nargs='*')
        parser.add_argument('--timeout',
                            default=10,
                            type=float,
                           )
        parser.add_argument('--lockout-key',
                            metavar='lockout_key',
                            default=None,
                            type=str,
                            help='string to provide in the RequestMessage.lockout_key, for locking endpoints or using locked endpoints',
                           )

class Get(GenericAgent):
    name = 'get'
class Set(GenericAgent):
    name = 'set'
class Config(GenericAgent):
    name = 'config'
    def __call__(self, kwargs):
        logger.warning("OP_CONFG is going to be deprecated, consider other usage")
        super(Config, self).__call__(kwargs)
class Run(GenericAgent):
    name = 'run'
class Cmd(GenericAgent):
    name = 'cmd'
__all__ += ['Get', 'Set', 'Config', 'Run', 'Cmd']

def agent_action(request_verb=None, args=None):
    if request_verb is None:
        raise exceptions.DriplineValueError('verb cannot be None')
    msgop = getattr(constants, 'OP_'+request_verb.upper())
    conn = Service(amqp_url = args.broker,
                   exchange = 'requests',
                   keys = '#'
                  )

    values = []
    payload = {}
    for val in args.values:
        temp_val = cast_arg(val)
        if isinstance(temp_val, types.StringType):
            if len(temp_val.split('=')) > 1:
                value = cast_arg('='.join(temp_val.split('=')[1:]))
                payload.update({temp_val.split('=')[0]:value})
            else:
                values.append(temp_val)
            
        else:
            values.append(temp_val)

    payload.update({'values':values})
    logger.debug('payload will be: {}'.format(payload))
    request = message.RequestMessage(msgop=msgop, payload=payload, lockout_key=args.lockout_key)
    try:
        reply = conn.send_request(args.target, request, timeout=args.timeout)
    except exceptions.DriplineException as dripline_error:
        logger.warning(dripline_error.message)
        return
    if not isinstance(reply, Message):
        result = Message.from_msgpack(reply)
    else:
        result = reply
    logger.info('response:\n{}'.format(result))
    print_prefix = '->'.join([args.target]+args.values)
    color = ''
    if not result.retcode == 0:
        color = '\033[91m'
    print('{color}{}(ret:{}): {}\033[0m'.format(print_prefix, result.retcode, result.payload, color=color))
    if result.return_msg is not '':
        logger.log(25, 'return message: {}'.format(result.return_msg))


if __name__ == '__main__':
    agent_doc = '''
                dripline_agent provides basic a CLI to the dripline system.
                '''
    parser = DriplineParser(description=agent_doc,
                            amqp_broker=True,
                            config_file=True,
                            tmux_support=True,
                            twitter_support=True,
                            extra_logger=logger,
                           )
    parser.add_argument('verb', choices=verb_list())
    parser.add_argument('target')
    parser.add_argument('values', nargs='*')
    parser.add_argument('--timeout',
                        default=10,
                        type=float,
                       )
    parser.add_argument('--lockout-key',
                        metavar='lockout_key',
                        default=None,
                        type=str,
                        help='string to provide in the RequestMessage.lockout_key, for locking endpoints or using locked endpoints',
                       )

    args = parser.parse_args()
    try:
        main(args)
    except KeyboardInterrupt:
        pass
