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
            ## SET options
            if 'default_set' in a_target:
                these_details.update({'default_set':a_target['default_set']})
            ## GET options
            these_details.update({'payload_field':a_target['payload_field']})
            if 'units' in a_target and 'formatter' in a_target:
                raise dripline.core.DriplineValueError('may not specify both "units" and "formatter"')
            if 'formatter' in a_target:
                these_details['formatter'] = a_target['formatter']
            elif 'units' in a_target:
                these_details['formatter'] = '{} -> {} [{}]'.format(a_target['target'], '{}', a_target['units'])
            else:
                these_details['formatter'] = '{} -> {}'.format(a_target['target'], '{}')
            ## CHECK options
            if 'tolerance' in a_target:
                these_details.update({'tolerance':a_target['tolerance']})
            else:
                these_details.update({'tolerance': 1.})
            if 'no_check' in a_target:
                these_details.update({'no_check':a_target['no_check']})
            else:
                these_details.update({'no_check':False})
            if 'get_target' in a_target:
                these_details.update({'get_name':a_target['get_target']})
            else:
                these_details.update({'get_name':a_target['target']})
            if 'target_value' in a_target:
                these_details.update({'target_value':a_target['target_value']})

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
            # checking the value of the endpoint
            if details['no_check']==True:
                logger.info('no check after set required: skipping!')
                continue
            else:
                value_get,a_rep = self._single_get(details['get_name'], details)

            if type(value_get) is unicode:
                logger.info('result in unicode')
                value_get = value_get.encode('utf-8')
            value_get_temp = value_get
            try:
                value_get = float(value_get_temp)
            except:
                logger.info('value get ({}) is not floatable'.format(value_get))
                value_get = value_get_temp

            # checking a target has been given (else use the endpoint used to set)
            if 'target_value' in details:
                target_value = details['target_value']
            else:
                logger.info('no target_value given: using value ({}) as a target_value to check'.format(value))
                target_value = value
            if value_get==None:
                raise dripline.core.DriplineValueError('value get is a None')

            # if the value we are checking is a float/int
            if isinstance(value_get, float) or isinstance(value_get, int):
                if  not isinstance(target_value,float) and not isinstance(target_value,int):
                    logger.warning('target is not the same type as the value get: going to use the set value ({}) as target_value'.format(value))
                    target_value = value
                if isinstance(target_value,float) or isinstance(target_value,int):
                    if 'tolerance' in details:
                        tolerance = details['tolerance']
                    else:
                        tolerance = None
                    if tolerance==None:
                        logger.info('No tolerance given: assigning an arbitrary tolerance (1.)')
                        tolerance = 1.
                    if not isinstance(tolerance,float) and not isinstance(tolerance,int) and not isinstance(tolerance,types.StringType):
                        logger.warning('tolerance is not a float or a string: assigning an arbitrary tolerance (1.)')
                        tolerance = 1.
                    if isinstance(tolerance,float) or isinstance(tolerance,int):
                        if tolerance == 0:
                            logger.info('tolerance zero inacceptable: setting tolerance to 1.')
                            tolerance = 1.
                        logger.info('testing a-t<b<a+t')
                        if target_value -  tolerance <= value_get and value_get <= target_value + tolerance:
                            logger.info('the value get ({}) is included in the target_value ({}) +- tolerance ({})'.format(value_get,target_value,tolerance))
                        else:
                            raise dripline.core.DriplineValueError('the value get ({}) is NOT included in the target_value ({}) +- tolerance ({}): stopping here!'.format(value_get,target_value,tolerance))
                    elif isinstance(tolerance,types.StringType):
                        if '%' not in tolerance:
                            logger.info('absolute tolerance')
                            tolerance = float(tolerance)
                        else:
                            logger.info('relative tolerance')
                            match_number = re.compile('-?\ *[0-9]+\.?[0-9]*(?:[Ee]\ *-?\ *[0-9]+)?')
                            tolerance = [float(x) for x in re.findall(match_number, tolerance)][0]*target_value/100.
                        if tolerance == 0:
                            logger.info('tolerance zero inacceptable: setting tolerance to 1.')
                            tolerance = 1.
                        logger.info('testing a-t<b<a+t')
                        if target_value -  tolerance <= value_get and value_get <= target_value + tolerance:
                            logger.info('the value get ({}) is included in the target_value ({}) +- tolerance ({})'.format(value_get,target_value,tolerance))
                        else:
                            raise dripline.core.DriplineValueError('the value get ({}) is NOT included in the target_value ({}) +- tolerance ({}): stopping here!'.format(value_get,target_value,tolerance))
                    else:
                        raise dripline.core.DriplineValueError('tolerance is not a float, int or string: stopping here')
                else:
                    raise dripline.core.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (float/int): stopping here!')

            # if the value we are checking is a string
            elif isinstance(value_get, types.StringType):
                if not isinstance(target_value,types.StringType):
                    logger.warning('target_value is not the same type as the value get: going to use the set value ({}) as target_value'.format(value))
                    target_value = value
                if isinstance(target_value,types.StringType):
                    target_backup = target_value
                    value_get_backup = value_get
                    # changing target in the dictionary
                    if target_value=='on' or target_value=='enable' or target_value=='enabled' or 'positive':
                        target_value=='1'
                    if target_value=='off' or target_value=='disable' or target_value=='disabled' or 'negative':
                        target_value=='0'
                    # changing value_get in the dictionary
                    if value_get=='on' or value_get=='enable' or value_get=='enabled' or 'positive':
                        value_get=='1'
                    if value_get=='off' or value_get=='disable' or value_get=='disabled' or 'negative':
                        value_get=='0'
                    # checking is target and value_get are the same
                    if target_value==value_get:
                        logger.info('value get ({}) corresponds to the target ({}): going on'.format(value_get_backup,target_value))
                    else:
                        raise dripline.core.DriplineValueError('value get ({}) DOES NOT correspond to the target_value ({}): stopping here!'.format(value_get_backup,target_value))
                else:
                    raise dripline.core.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (string): stopping here!')

            # if the value we are checking is a bool
            elif isinstance(value_get, bool):
                if not isinstance(target_value,bool):
                    logger.warning('target_value is not the same type as the value get: going to use the set value ({}) as target_value'.format(value))
                    target_value = value
                if isinstance(target_value,bool):
                    if value_get==target_value:
                        logger.info('value get ({}) corresponds to the target ({}): going on'.format(value_get,target_value))
                    else:
                        raise dripline.core.DriplineValueError('value get ({}) DOES NOT correspond to the target ({}): stopping here!'.format(value_get,target_value))
                else:
                    raise dripline.core.DriplineValueError('Cannot check! value set and target are not the same type as value get (string): stopping here!')

            # if you are in this "else", this means that you either wanted to mess up with us or you are not viligant enough
            else:
                raise dripline.core.DriplineValueError('value get ({}) is not a float, int, string, bool, None ({}): SUPER WEIRD!'.format(value_get,type(value_get)))

            logger.info('{} set to {}'.format(a_target,value_get))

        return 'done'

    def _single_set(self, endpoint_name, value):
        '''
        attempt to set a single endpoint
        '''
        ret_val = None
        ret_rep = ''
        a_result = self.portal.send_request(request=dripline.core.RequestMessage(msgop=dripline.core.OP_SET, payload={'values':[value]}), target=endpoint_name)

        return a_result
