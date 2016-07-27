from __future__ import absolute_import
__all__ = []

import dripline

import logging

logger = logging.getLogger(__name__)


__all__.append('MultiDo')
@dripline.core.fancy_doc
class MultiDo(dripline.core.Endpoint):
    '''
    MultiSet is a convenience object allowing a single target to be
    used to set multiple endpoints. The intended use is specifically
    for setting many endpoints, and use cases for other verbs are not considered.
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
            these_details.update({'payload_field':a_target['payload_field']})
            if 'units' in a_target and 'formatter' in a_target:
                raise dripline.core.DriplineValueError('may not specify both "units" and "formatter"')
            if 'formatter' in a_target:
                these_details['formatter'] = a_target['formatter']
            elif 'units' in a_target:
                these_details['formatter'] = '{} -> {} [{}]'.format(a_target['target'], '{}', a_target['units'])
            else:
                these_details['formatter'] = '{} -> {}'.format(a_target['target'], '{}')
            self._targets.append([a_target['target'], these_details])

    def on_get(self):
        result_vals = {}
        result_reps = []
        for a_target,details in self._targets:
            a_val,a_rep = self._single_get(a_target, details)
            result_vals[a_target] = a_val
            result_reps.append(a_rep)
        return {'value_raw': result_vals, 'value_cal': '\n'.join(result_reps)}

    def _single_get(self, endpoint_name, details):
        '''
        attempt to get a single endpoint and return a tuple of (desired_value, string_rep)
        '''
        ret_val = None
        ret_rep = ''
        a_result = self.portal.send_request(request=dripline.core.RequestMessage(msgop=dripline.core.OP_GET), target=endpoint_name)
        if a_result.retcode != 0:
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
        else:
            ret_val = a_result.payload[details['payload_field']]
            ret_rep = details['formatter'].format(ret_val)

        return ret_val,ret_rep

    def on_set(self, value):

        to_be_sent = []
        for a_target,details in self._targets:
            if 'default_set' in details:
                value_to_set = details['default_set']
            else:
                value_to_set = value

            result = self._single_set(a_target, value_to_set)
            if result.retcode !=0:
                logger.warning('unable to set <{}>'.format(a_target))
                raise dripline.core.exception_map[result.retcode](result.return_msg)

        return 'done'

    def _single_set(self, endpoint_name, value):
        '''
        attempt to set a single endpoint
        '''
        ret_val = None
        ret_rep = ''
        a_result = self.portal.send_request(request=dripline.core.RequestMessage(msgop=dripline.core.OP_SET, payload={'values':[value]}), target=endpoint_name)

        return a_result
