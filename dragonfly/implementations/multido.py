'''
Convenience object allowing a single target to interact with multiple endpoints
'''

from __future__ import absolute_import
__all__ = []

from dripline.core import Endpoint, fancy_doc, exceptions

import logging

logger = logging.getLogger(__name__)


__all__.append('MultiDo')
@fancy_doc
class MultiDo(Endpoint):
    '''
    MultiDo is a convenience object allowing a single target to interact with
    multiple endpoints. MultiDo serves as the generic implementation with both
    get and set methods, specific implementations of MultiGet or MultiSet will
    limit this functionality for particular use cases.

    For get, the calibrated value returned is intended to be a nicely formatted
    string representation of the result, while the raw value will retain the
    types of those values returned. A "payload_field" should be specified for
    each target. Either a "formatter" or "units" specifier may be given for each
    target for further detailing the calibrated return value.

    For set, each target can have a "default_set" or adopt the given value.  The
    set_and_check feature is implemented, which can be bypassed with the
    "no_check" option, or loosened with a "tolerance" value.  For endpoints
    requiring a separate endpoint to be checked, the "get_name" and
    "target_value" arguments are provided.
    '''
    def __init__(self, targets=[], **kwargs):
        '''
        targets (list): list of dictionaries which must provide a value for 'target', other optional fields:
          default_set: always set endpoint to this value
          payload_field (str): return payload field to get (value_cal, value_raw, or values)
          units (str): display units for 'calibrated' return value
          formatter (str): special formatting for 'calibrated' return string
          tolerance: check tolerance
          no_check (bool): disable set_and_check; necessary for set-only endpoints!
          get_target (str): endpoint to get for check (default is 'target')
          target_value: alternate value to check against
        '''
        Endpoint.__init__(self, **kwargs)
        self._targets = []
        for a_target in targets:
            these_details = {}
            ## SET options
            if 'default_set' in a_target:
                these_details.update({'default_set':a_target['default_set']})
            ## GET options
            if 'payload_field' in a_target:
                these_details.update({'payload_field':a_target['payload_field']})
            else:
                these_details.update({'payload_field':'value_cal'})
            if 'units' in a_target and 'formatter' in a_target:
                raise exceptions.DriplineValueError('may not specify both "units" and "formatter"')
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
                these_details.update({'tolerance': 0.99})
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
        '''
        attemps to get a single endpoint and return value and string representation for every target
        '''
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
        try:
            a_result = self.provider.get(target=endpoint_name)
            ret_val = a_result[details['payload_field']]
            ret_rep = details['formatter'].format(ret_val)
        except exceptions.DriplineException as err:
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, err.retcode, err)
        return ret_val,ret_rep

    def on_set(self, value):
        '''
        Performs sets and checks ... #TODO_DOC
        '''

        to_be_sent = []
        for a_target,details in self._targets:
            if 'default_set' in details:
                value_to_set = details['default_set']
            else:
                value_to_set = value
            logger.info('setting <{}>'.format(a_target))
            result = self.provider.set(a_target, value_to_set)
            # checking the value of the endpoint
            if details['no_check']==True:
                logger.info('no check after set required: skipping!')
                continue
            else:
                logger.info('checking <{}>'.format(a_target))
                value_get,a_rep = self._single_get(details['get_name'], details)

            if type(value_get) is unicode:
                logger.debug('result in unicode')
                value_get = value_get.encode('utf-8')
            value_get_temp = value_get
            try:
                value_get = float(value_get_temp)
            except:
                logger.debug('value get ({}) is not floatable'.format(value_get))
                value_get = value_get_temp

            # checking a target has been given (else use the endpoint used to set)
            if 'target_value' in details:
                target_value = details['target_value']
            elif 'default_set' in details:
                logger.info('default_set ({}) given for <{}>: using this as target_value'.format(details['default_set'],a_target))
                target_value = details['default_set']
            else:
                logger.debug('no target_value given: using value ({}) as a target_value to check'.format(value))
                target_value = value
            if value_get==None:
                raise exceptions.DriplineValueError('value get is a None')

            # if the value we are checking is a float/int
            if isinstance(value_get, (int,float)):
                if not isinstance(target_value, (int,float)):
                    try:
                        target_value = float(target_value)
                    except ValueError:
                        logger.warning('target <{}> is not the same type as the value get: going to use the set value ({}) as target_value'.format(a_target,value))
                        target_value = value
                if isinstance(target_value, (int,float)):
                    if 'tolerance' in details:
                        tolerance = details['tolerance']
                    else:
                        tolerance = None
                    if tolerance==None:
                        logger.debug('No tolerance given: assigning an arbitrary tolerance (1.)')
                        tolerance = 1.
                    if not isinstance(tolerance,float) and not isinstance(tolerance,int) and not isinstance(tolerance,str):
                        logger.warning('tolerance is not a float or a string: assigning an arbitrary tolerance (1.)')
                        tolerance = 1.
                    if isinstance(tolerance,float) or isinstance(tolerance,int):
                        if tolerance == 0:
                            logger.debug('tolerance zero inacceptable: setting tolerance to 1.')
                            tolerance = 1.
                        logger.debug('testing a-t<b<a+t')
                        if target_value -  tolerance <= value_get and value_get <= target_value + tolerance:
                            logger.info('the value get <{}> ({}) is included in the target_value ({}) +- tolerance ({})'.format(a_target,value_get,target_value,tolerance))
                        else:
                            raise exceptions.DriplineValueError('the value get <{}> ({}) is NOT included in the target_value ({}) +- tolerance ({}): stopping here!'.format(a_target,value_get,target_value,tolerance))
                    elif isinstance(tolerance,str):
                        if '%' not in tolerance:
                            logger.debug('absolute tolerance')
                            tolerance = float(tolerance)
                        else:
                            logger.debug('relative tolerance')
                            match_number = re.compile('-?\ *[0-9]+\.?[0-9]*(?:[Ee]\ *-?\ *[0-9]+)?')
                            tolerance = [float(x) for x in re.findall(match_number, tolerance)][0]*target_value/100.
                        if tolerance == 0:
                            logger.debug('tolerance zero inacceptable: setting tolerance to 1.')
                            tolerance = 1.
                        logger.debug('testing a-t<b<a+t')
                        if target_value -  tolerance <= value_get and value_get <= target_value + tolerance:
                            logger.info('the value <{}> get ({}) is included in the target_value ({}) +- tolerance ({})'.format(a_target,value_get,target_value,tolerance))
                        else:
                            raise exceptions.DriplineValueError('the value <{}> get ({}) is NOT included in the target_value ({}) +- tolerance ({}): stopping here!'.format(a_target,value_get,target_value,tolerance))
                    else:
                        raise exceptions.DriplineValueError('tolerance is not a float, int or string: stopping here')
                else:
                    raise exceptions.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (float/int): stopping here!')

            # if the value we are checking is a string
            elif isinstance(value_get, str):
                target_backup = target_value
                value_get_backup = value_get

                if value_get=='on' or value_get=='enable' or value_get=='enabled' or value_get == 'positive':
                    value_get=1
                elif value_get=='off' or value_get=='disable' or value_get=='disabled' or value_get == 'negative':
                    value_get=0

                if isinstance(target_value,str):
                    # changing target in the dictionary
                    if target_value=='on' or target_value=='enable' or target_value=='enabled' or target_value == 'positive':
                        target_value=1
                    if target_value=='off' or target_value=='disable' or target_value=='disabled' or target_value ==  'negative':
                        target_value=0
                    # raise exceptions.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (string): stopping here!')
                    # checking is target and value_get are the same

                if target_value==value_get:
                    logger.info('value get ({}) corresponds to the target ({}): going on'.format(value_get_backup,target_backup))
                else:
                    raise exceptions.DriplineValueError('value get ({}) DOES NOT correspond to the target_value ({}): stopping here!'.format(value_get_backup,target_backup))

            # if the value we are checking is a bool
            elif isinstance(value_get, bool):
                if not isinstance(target_value,bool):
                    logger.warning('target_value is not the same type as the value get: going to use the set value ({}) as target_value'.format(value))
                    target_value = value
                if isinstance(target_value,bool):
                    if value_get==target_value:
                        logger.info('value get ({}) corresponds to the target ({}): going on'.format(value_get,target_value))
                    else:
                        raise exceptions.DriplineValueError('value get ({}) DOES NOT correspond to the target ({}): stopping here!'.format(value_get,target_value))
                else:
                    raise exceptions.DriplineValueError('Cannot check! value set and target are not the same type as value get (string): stopping here!')

            # if you are in this "else", this means that you either wanted to mess up with us or you are not viligant enough
            else:
                raise exceptions.DriplineValueError('value get ({}) is not a float, int, string, bool, None ({}): SUPER WEIRD!'.format(value_get,type(value_get)))

            logger.info('{} set to {}'.format(a_target,value_get))

        return 'set and check successful'


__all__.append('MultiGet')
@fancy_doc
class MultiGet(MultiDo):
    '''
    Identical to MultiDo, but with an explicit exception if on_set is attempted.
    '''
    def __init__(self, **kwargs):
        MultiDo.__init__(self, **kwargs)

    def on_set(self, value):
        logger.warning("Disallowed method: attempt to set MultiGet endpoint {}".format(self.name))
        raise exceptions.DriplineMethodNotSupportedError('setting not available for {}'.format(self.name))


__all__.append('MultiSet')
@fancy_doc
class MultiSet(MultiDo):
    '''
    Identical to MultiDo, but with an explicit exception if on_get is attempted and forced no_check on all targets.
    MultiDo's on_get method has error handling, so this method only useful to globally apply no_check option.
    '''
    def __init__(self, **kwargs):
        for a_target in kwargs['targets']:
            if 'no_check' in a_target and a_target['no_check']==False:
                logger.critical("MultiSet forces no_check option for all endpoints.  Option for {} of {} overridden.".format(a_target['target'],kwargs['name']))
            a_target.update({'no_check':True})
        MultiDo.__init__(self, **kwargs)

    def on_get(self):
        logger.warning("Disallowed method: attempt to get MultiSet endpoint {}".format(self.name))
        raise exceptions.DriplineMethodNotSupportedError('getting not available for {}'.format(self.name))
