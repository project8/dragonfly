from __future__ import absolute_import
__all__ = []

import dripline

import logging

logger = logging.getLogger(__name__)


__all__.append('MultiGet')
@dripline.core.fancy_doc
class MultiGet(dripline.core.Endpoint):
    '''
    MultiGet is a convenience object allowing a single target to be
    used to access the result of "get"ting multiple endpoints. The
    intended use is specifically for collecting the current value of 
    many endpoints, and use cases for other verbs are not considered.

    The calibrated value returned is intended to be a nicely formatted
    string representation of the result, while the raw value will
    retain the types of those values returned.
    '''
    def __init__(self, targets={}, **kwargs):
        '''
        targets (dict): dictionary where keys are endpoint names to get and values are themselves dictionaries which must provide a value for 'payload_field' and may provide either a 'units' field (for use with the default format string) or a 'formatter' field which is a format string which takes one insertion for the get result
        '''
        dripline.core.Endpoint.__init__(self, **kwargs)

        self._targets = {}
        for a_name,details in targets.items():
            these_details = {'payload_field':details['payload_field']}
            if 'units' in details and 'formatter' in details:
                raise dripline.core.DriplineValueError('may not specify both "units" and "formatter"')
            if 'formatter' in details:
                these_details['formatter'] = details['formatter']
            elif 'units' in details:
                these_details['formatter'] = '{} -> {} [{}]'.format(a_name, '{}', details['units'])
            else:
                these_details['formatter'] = '{} -> {}'.format(a_name, '{}')
            self._targets[a_name] = these_details

        self._request_message = dripline.core.RequestMessage(msgop=dripline.core.OP_GET)

    def on_get(self):
        result_vals = {}
        result_reps = []
        for a_target in self._targets:
            a_val,a_rep = self._single_get(a_target)
            result_vals[a_target] = a_val
            result_reps.append(a_rep)
        return {'value_raw': result_vals, 'value_cal': '\n'.join(result_reps)}

    def _single_get(self, endpoint_name):
        '''
        attempt to get a single endpoint and return a tuple of (desired_value, string_rep)
        '''
        ret_val = None
        ret_rep = ''
        a_result = self.portal.send_request(request=self._request_message, target=endpoint_name)
        if a_result.retcode != 0:
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
        else:
            ret_val = a_result.payload[self._targets[endpoint_name]['payload_field']]
            ret_rep = self._targets[endpoint_name]['formatter'].format(ret_val)
        
        return ret_val,ret_rep
