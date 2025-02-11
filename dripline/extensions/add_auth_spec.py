'''
Contains the AddAuthSpec class, for adding authentication specifications
'''

import dripline.implementations
import scarab

import logging

logger = logging.getLogger(__name__)

__all__ = []

__all__.append('AddAuthSpec')
class AddAuthSpec(dripline.implementations.BaseAddAuthSpec):
    '''

    '''

    def __init__(self, app):
        '''
        '''
        dripline.implementations.BaseAddAuthSpec.__init__(self, app)
        self.add_slack_auth_spec(app)

    def add_slack_auth_spec(self, app):
        '''
        Adds the Slack authenticaiton specification to a scarab::main_app object
        '''
        auth_spec = {
            'dripline': {
                'default': 'default-token',
                'env': 'DRIPLINE_SLACK_TOKEN',
            },
        }
        app.add_default_auth_spec_group( 'slack', scarab.to_param(auth_spec).as_node() )
        logger.debug('Added slack auth spec')
