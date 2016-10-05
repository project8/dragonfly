from __future__ import absolute_import
__all__ = []

import dripline

import logging

logger = logging.getLogger(__name__)


__all__.append('MultiSet')
@dripline.core.fancy_doc
class MultiSet(dripline.core.Endpoint):
    '''
    MultiSet is a convenience object allowing a single target to be
    used to set multiple endpoints. The intended use is specifically
    for setting many endpoints, and use cases for other verbs are not considered.
    This is a very primitive version of MultiDo, since it does not integrate the set_and_check feature.
    We should keep it because it is working.
    '''
    def __init__(self, targets=[], **kwargs):
        '''
        targets (list): list of two element lists where the first elements are endpoint names to set and second elements are themselves dictionaries which must provide a value for 'payload_field'
        '''
        dripline.core.Endpoint.__init__(self, **kwargs)

        self._targets = []
        for a_target in targets:
            these_details = {}
            if 'default_set' in a_target:
                these_details.update({'default_set':a_target['default_set']})
            self._targets.append([a_target['target'], these_details])


    def on_set(self, value):

        to_be_sent = []
        for a_target,details in self._targets:
            if 'default_set' in details:
                value_to_set = details['default_set']
            else:
                value_to_set = value

            result = self.provider.set(a_target, value_to_set)

        return 'done'

