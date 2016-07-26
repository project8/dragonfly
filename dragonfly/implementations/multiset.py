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
    '''
    def __init__(self, targets=[], **kwargs):
        '''
        targets (list): list of two element lists where the first elements are endpoint names to set and second elements are themselves dictionaries which must provide a value for 'payload_field'
        '''
        dripline.core.Endpoint.__init__(self, **kwargs)

        self._targets = []
        self._list_flag=[]
        #for a_name,details in targets:
        these_details = {}
        for a_target in targets:
            print(a_target['target'])

            if 'default_set' in a_target:
                these_details.update({'default_set':a_target['default_set']})

            if 'format_target' in a_target:
                these_details.update({'format_target':a_target['format_target']})
            # if 'units' in a_target and 'formatter' in a_target:
            #     raise dripline.core.DriplineValueError('may not specify both "units" and "formatter"')
            # if 'formatter' in a_target:
            #     these_details['formatter'] = a_target['formatter']
            # elif 'units' in a_target:
            #     these_details['formatter'] = '{} -> {} [{}]'.format(a_target['target'], '{}', a_target['units'])
            # else:
            #     these_details['formatter'] = '{} -> {}'.format(a_target['target'], '{}')
            self._targets.append([a_target['target'], these_details])

        self._request_message = dripline.core.RequestMessage(msgop=dripline.core.OP_SET)

    def update_parser(self,parser):
        for flag in parser_new_flags:
            if isinstance(flag,str):
                parser.add_argument(flag)
            self._list_flag.append(flag)
        parser.add_argument('value_to_set')

    def on_set(self, **kwargs):

        to_be_sent = []
        for a_target,details in self._targets:
            if 'default_set' in details:
                value = details['default_set']
            else:
                value = kwargs.value_to_set
            # print(value)
            if 'format_target' in details:
                target = a_target.format(details['format_target'])
            else:
                target = a_target
            print(value,target)

            # result = self._single_set(a_target, value_to_set)
            if result.retcode !=0:
                logger.warning('unable to set <{}>'.format(a_target['target']))
                raise dripline.core.exception_map[result.retcode](result.return_msg)

        # return {'value_raw': result_vals, 'value_cal': '\n'.join(result_reps)}

    def _single_set(self, endpoint_name, details):
        '''
        attempt to set a single endpoint
        '''
        ret_val = None
        ret_rep = ''
        a_result = self.portal.send_request(request=self._request_message, target=endpoint_name)
        if a_result.retcode != 0:
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
        else:
            ret_val = a_result.payload[details['payload_field']]
            ret_rep = details['formatter'].format(ret_val)

        return ret_val,ret_rep
