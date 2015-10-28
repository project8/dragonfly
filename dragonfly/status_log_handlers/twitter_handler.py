'''
Wrappers for the standard logging module classes
'''

from __future__ import absolute_import

import os

import logging

__all__ = []


__all__.append('TwitterHandler')
class TwitterHandler(logging.Handler):
    '''
    A custom message handler for redirecting text to twitter
    '''
    argparse_flag_str = 'twitter'

    def emit(self, record):
        try:
            import TwitterAPI, yaml, os
            auth_kwargs = yaml.load(open(os.path.expanduser('~/.twitter_authentication.yaml')))
            api = TwitterAPI.TwitterAPI(**auth_kwargs)
            tweet_text = '{} #SCAlert'.format(self.format(record)[:100])
            api.request('statuses/update', {'status': tweet_text})
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def update_parser(self, parser):
        parser.add_argument('--'+self.argparse_flag_str,
                            action='store_true',
                            help='enable a status log handler to post messages to twitter',
                           )

