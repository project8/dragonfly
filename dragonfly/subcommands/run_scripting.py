'''
Overview
~~~~~~~~

A YAML parser which defines a syntax for writing run "scripts." This should in principle
make it possible to define any data acquisition task (which might take hours or
even multiple days) in advance and have it proceed fully automatically. Furthermore,
"standard" run sets (such as calibrations) could be fully standardized and the same
run file used every time.

As with everything else, YAML will be the tested and preferred format for these files
(since json doesn't support comments). But of course json is a subset of YAML.

In addition to the configuration file itself, there are several runtime options. These
are listed here and maintained as part of the argparse help fields.
    - `--force-restart` (`-f`)
    - `--dry-run` (`-d`)


Input File
~~~~~~~~~~

The file should parse to a list of dictionaries. Each of these dictionaries will define
a type of action to take, in order from the file, with various configurable parameters.
Each *must* specify the action by including the key "action" with one of the following
values. The required and optional configurations for each are described further below.

    action: {pause_for_user, sleep, lockout, set, cmd, do, esr_run, single_run, multi_run}

That is, at the highest level, the file should look like::

    - action: VALUE_FROM_ABOVE
      ...
    - action: VALUE_FROM_ABOVE
      ...
    ...


Throughout the documentation for valid actions, we adopt some conventions to indicate
how you should fill in information (we used some of them above). I'll try to describe in
the following bullet list:

- items in ALL_CAPITALS indicate that you need to provide the value.
- an elipsis (...) indicates that the list of entries may be extended, following preceding pattern
- sometimes it may not be obvious what the "type" of a value may be named within parenthesis ();
  multiple valid types will be separated with || (a syntax for "or" in some programming languages);
  this will come before the ALL_CAPS_INDICATION_TO_ADD_A_VALUE
- sometimes the valid value for a parameter must come from a limited set. This will follow the
  pattern as above for types, but will use a forward slash (/) to separate valid values.
- sometimes named configuration fields are optional. This will be indicated by a default value
  listed in parenthesis after the ALL_CAPS_INDICATION_TO_ADD_A_VALUE if it is single-valued, or on
  the line with the key if it takes multiple values (which will be described on subsequent lines).
  Note that sometimes the default behavior is not to include the entry at all (this is not the
  same as 0, or None); such a case is indicated by "(default: )"
- sometimes both the key and value must be provided, in this case the entire entry will be
  enclosed in parenthesis (the description paragraph should also explain this).

Let's take an example. The following is a contrived example configuration description,
followed by a valid block based on it.::

  - action: profit
    currency: (dollar/bitcoin/euro) VALUE (default: dollar)
    rounding: VALUE (default: 0.05)
    suppliers:
      - SUPPLIER_NAME
      ...
    product_map: (default: {})
      PRODUCT_NAME: (number) PRODUCT_PRICE
      ...


A valid example would then be::

  - action: profit
    currency: dollar
    suppliers:
      - amazon
      - walmart
      - mcmaster
    product_map:
      bolts: 1.53
      washers: 0.62
      nuts: 0.77
      paper_towels: 2.50

or another (with minimum fields)::

  - action: profit
    suppliers:
      - ebay

The documentation for each action is kept with its implementing method as a doc string.
In each case, the method is named with the prefix `action_`
---

'''

from __future__ import absolute_import

import os, sys
import datetime
import json
import logging
import time
import uuid
from six import string_types
import re as re


try:
    import asteval
    import yaml
except ImportError:
    pass

import dripline

logger = logging.getLogger(__name__)

__all__ = []

__all__.append('RunScript')
class RunScript(object):
    '''
    use execution script to configure system state and take data
    '''
    name = 'execute'

    def __init__(self, *args, **kwargs):
        if not 'asteval' in globals():
            raise ImportError("asteval not found but is a required dependency for RunScript")
        if not 'yaml' in globals():
            raise ImportError("yaml not found but is a required dependency for RunScript")
        self.cache_attributes = [
                                 '_lockout_key',
                                 '_last_action',
                                 '_action_cache',
                                 '_to_unlock',
                                ]
        self._lockout_key = None
        self._last_action = -1
        self._action_cache = {}
        self._to_unlock = []
        self.interface = None
        self._cache_file_name = '/tmp/execution_cache.json'
        self._dry_run_mode = False

        self.evaluator = asteval.Interpreter()
        self.evaluator.symtable['datetime'] = datetime


    def init_cache_file(self, execution_file):
        cache_file_name = execution_file
        if execution_file.count('.') == 1:
            cache_file_name = cache_file_name[0:cache_file_name.find('.')]
        else:
            logger.debug('cannot parse execution_file punctuation: {}'.format(execution_file))
            cache_file_name = ""
        if cache_file_name.find('/') != -1:
            cache_file_name = cache_file_name[cache_file_name.rfind('/')+1:len(cache_file_name)]

        if cache_file_name != '':
            self._cache_file_name = '/tmp/'+cache_file_name+'_cache.json'
            logger.info('new cache file is {}'.format(self._cache_file_name))
        else:
            self._cache_file_name = '/tmp/execution_cache.json'
            logger.debug('empty cache_file_name: using default {}'.format(self._cache_file_name))

    def update_from_cache_file(self):
        try:
            cache_file = open(self._cache_file_name, 'r')
            cache = json.load(cache_file)
            cache_file.close()
            for key,value in cache.items():
                if key in self.cache_attributes:
                    setattr(self, key, value)
            if self._lockout_key is not None:
                self.action_lockout(endpoints=self._to_unlock)
        except IOError:
            # file doesn't exist assume starting from the beginning
            pass

    def remove_cache(self):
        try:
            logger.info('removing cache file {}'.format(self._cache_file_name))
            os.remove(self._cache_file_name)
        except OSError:
            logger.debug('cannot remove the cache file (maybe the file does not exist)')

    def update_parser(self, parser):
        parser.add_argument('execution_file',
                            help='file containing the detailed execution steps',
                           )
        parser.add_argument('-f','--force-restart',
                            action='store_true',
                            default = False,
                            help='force execution to restart the  execution script from the beginning, regardless of its previous completion status',
                           )
        parser.add_argument('-d','--dry-run',
                            action='store_true',
                            default = False,
                            help='flag which prevents the daq from taking data by overriding start_timed_run',
                           )

    def __call__(self, kwargs):
        if not 'broker' in kwargs:
            kwargs.broker = 'localhost'
        if kwargs.broker is None:
            kwargs.broker = 'localhost'
        # create interface
        self.interface = dripline.core.Interface(amqp_url=kwargs.broker, name='execution_script')
        # update self from cache file unless there is the --force-restart option
        self.init_cache_file(kwargs.execution_file)
        if kwargs.force_restart:
            self.remove_cache()
        else:
            self.update_from_cache_file()
        if kwargs.dry_run:
            logger.info('dry run mode activated: no run will be launched!')
            self._dry_run_mode = True
        try:
            # do each of the actions listed in the execution file
            actions = yaml.safe_load(open(kwargs.execution_file))
            if self._last_action == len(actions)-1:
                logger.debug('cache file indicates this execution is already complete')
                return
            for i_action,action in enumerate(actions):
                logger.info('doing action [{}]: {}'.format(i_action, action['action']))
                # sip if we're resuming an action
                if i_action <= self._last_action:
                    logger.info('skipping')
                    continue
                #########################
                # actually do actions
                method_name = 'action_' + action.pop('action')
                this_method = getattr(self, method_name, False)
                if not this_method:
                    logger.debug('action <{}> not supported, perhaps your execution file has a typo?'.format(method_name.replace('action_','')))
                    raise dripline.core.DriplineMethodNotSupportedError('RunScript class has no method <{}>'.format(method_name))
                this_method(**action)
                self._last_action = i_action
                self._action_cache = {}
                self.update_cache()
        # except block as in dripline_agent to spam error message
        except dripline.core.DriplineException as dripline_error:
            logger.critical("run script crashing with error: {}".format(dripline_error.message))
            raise dripline.core.exception_map[dripline_error.retcode](dripline_error.message, dripline_error.result)
        # finally, unlock anything we locked (even if there's an exception along the way)
        finally:
            if self._lockout_key is not None:
                self.do_unlocks()
        logger.info('execution complete')
        # remove the cache to prepare for a new execution script
        self.remove_cache()
        logger.info('Execution script is over! Good job!')


    def update_cache(self):
        to_dump = {}
        for attribute in self.cache_attributes:
            to_dump[attribute] = getattr(self, attribute)
        fp = open(self._cache_file_name, 'w')
        json.dump(obj=to_dump, fp=fp, indent=4)
        fp.flush()
        fp.truncate()
        fp.close()

    def action_pause_for_user(self, message, **kwargs):
        '''
        print a message to the user and wait for a response. The content
        of the user's reply will not be stored or used. This allows indefinate pauses
        for user action. For example, changing the vertical position of the insert, which
        has to be done manually. Any result of the user action which needs to be measured
        should still be done automatically (using loggers, sets/cmds to endpoints, etc.)

        Configfile entry::

            - action: pause_for_user
              message: STRING_TO_PRINT_PRIOR_TO_PAUSE
        '''


        # note, this is python2 specific... (in python3 it is input not raw_input
        # but python2 has something different named input
        userinput = 0
        while userinput != 'y':
            userinput = str.lower(raw_input('{}\n(Type \'y\' to continue)\n'.format(message)))

    def action_sleep(self, duration, **kwargs):
        '''
        wait for specified period of time

        Configfile entry::

            - action: sleep
              duration: (int||float) THE_DURATION
        '''
        if isinstance(duration,int) or isinstance(duration,float):
            logger.info("Sleeping for {} sec, ignoring args: {}".format(duration, kwargs))
        else:
            raise dripline.core.DriplineValueError('duration is not a float/int')
        time.sleep(duration)

    def action_lockout(self, endpoints=[], lockout_key=None, **kwargs):
        '''
        send a lockout command to the specified list of endpoints. If a lockout
        action is called, all subsequent requests will use the automatically generated
        key. An unlock will automatically be called at the end of execution. If a
        lockout_key is not given (or is None), one will be generated and cached.

        Configfile entry::

            - action: lockout
              lockout_key: KEY (default: None)
              endpoints: (default: [])
                - NAME
                  ...
        '''
        if lockout_key is not None:
            self._lockout_key = lockout_key
        if self._lockout_key is None:
            self._lockout_key = uuid.uuid4().get_hex()
        logger.info('locking with key: {}'.format(self._lockout_key))
        logger.info('endpoints are: {}'.format(endpoints))
        for target in endpoints:
            result = self.interface.cmd(target, 'lock', lockout_key=self._lockout_key)
            if result.retcode == 0:
                if target not in self._to_unlock:
                    self._to_unlock.append(target)
            else:
                logger.debug('unable to lock <{}>'.format(target))
                raise dripline.core.exception_map[result.retcode](result.return_msg)

    def action_cmd(self, cmds, **kwargs):
        '''
        send a cmd request to an existing endpoint. The key ARGUMENT names an
        argument that will be given to the method and ARG_VALUE is the value it will be assigned
        For example, one can use "action_cmd" to start_timed_run (even if this is unoptimzed) by assigning:
        "endpoint: daq_target", "method_name: start_timed_run", "run_name: name_of_the_run",
        "run_time: duration_of_the_run". The asteval_format behavior is a feature which is known to be very
        subtle. It is itself a dictionary, which allows the value of other keys within the command dictionary
        itself to be modified/computed at run time. This is used, for example, to determine a datetime
        which is a certain amount of time in the future, relative to the execution datetime of the cmd.

        Configfile entry::

            - action: cmd
              cmds:
                - endpoint: ENDPOINT_NAME
                  timeout: DURATION (default: )
                  asteval_format: (default: {})
                  method_name: METHOD
                  (ARGUMENT: ARG_VALUE)
                  ...
                ...
        '''
        # mandatory fields are <endpoint> and <method_name> for each cmd
        logger.info('doing cmd block')
        for this_cmd in cmds:
            cmd_kwargs = this_cmd.copy()
            if 'timeout' in cmd_kwargs:
                logger.debug('timeout set to {}'.format(cmd_kwargs['timeout']))
            reformat = cmd_kwargs.pop('asteval_format',{})
            for key in reformat:
                decoded = self.evaluator(reformat[key])
                if decoded is not None:
                    logger.debug('{} set to {} from {}'.format(key,decoded,reformat[key]))
                    cmd_kwargs.update( {key:decoded} )
                else:
                    raise dripline.core.DriplineValueError('Cannot reformat {}:{}, type is {}'.format(key,reformat[key],type(reformat[key])))
            logger.info('sending cmd {}.{}'.format(cmd_kwargs['endpoint'],cmd_kwargs['method_name']))
            self.interface.cmd(**cmd_kwargs)

    def action_set(self, sets, **kwargs):
        '''
        a list of sets to assign new endpoint values. There is also support for
        ensuring the desired state has been reached. This check can be done using a different
        endpoint (for example, the actual current output of trap_coil_X can be checked using
        trap_coil_X_current_output after setting trap_coil_X_current_limit). If no endpoint name
        is given in "get_name", the check will use the endpoint used to set the value.
        One can define target_value to be compared with the get_value; if None, the set_value is used.
        The target_value can be a bool, string, float/int. Warning, some strings have been determined to
        be "special" (on/of, enable/disable, enabled/disabled, positive/negative) and will be translated
        to either '1' or '0'. This is a recurring source of confusion and should be refactored, such
        a project is non-trivial because of the amount of existing logic and the fact that it would
        break previously working run scripts.
        The check can use the raw or calibrated value of the get_value.
        The tolerance between a "target_value" and the "value_get" can be set in an
        absolute scale (ex/default: 1) or a relative one (ex/default: 5%).
        The automatic check after the set of a specific endpoint can be disabled by
        adding a "no_check: True" to the endpoint set.

        Configfile entry::

            - action: set
              sets:
                - name: ENDPOINT_NAME
                  value: NEW_VALUE
                  timeout: DURATION (default: )
                  no_check: (True/False) SELECTION (default: False)
                  sleep_time_before_check: DURATION (default: )
                  get_name: NAME (default: )
                  payload_field: (value_raw/value_cal) FIELD_NAME (default: )
                  target_value: TARGET_OF_SET (default: )
                  tolerance: TOLERANCE (default: 1.)
        '''
        logger.info('doing set block')
        set_kwargs = {'endpoint':None, 'value':None}
        get_kwargs = {'endpoint':None}
        if self._lockout_key:
            set_kwargs.update({'lockout_key':self._lockout_key})
            get_kwargs.update({'lockout_key':self._lockout_key})
        for this_set in sets:
            logger.info('setting {}->{}'.format(this_set['name'], this_set['value']))
            set_kwargs.update({'endpoint':this_set['name'],'value':this_set['value']})
            if 'timeout' in this_set:
                logger.debug('timeout set to {}'.format(this_set['timeout']))
                set_kwargs.update({'timeout':this_set['timeout']})
            result = self.interface.set(**set_kwargs)
            if result.retcode == 0:
                logger.debug('...set of {}->{} complete'.format(this_set['name'], this_set['value']))
            else:
                logger.critical('unable to set <{}>'.format(this_set['name']))
                raise dripline.core.exception_map[result.retcode](result.return_msg)
            if 'no_check' in this_set:
                if this_set['no_check']==True:
                    logger.info('no check requested: skipping!')
                    continue
            if 'sleep_time_before_check' in this_set:
                logger.info('sleeping for {} s before check'.format(this_set['sleep_time_before_check']))
                self.action_sleep(this_set['sleep_time_before_check'])
            if 'get_name' in this_set:
                logger.debug('checking the set value using {}'.format(this_set['get_name']))
                get_kwargs.update({'endpoint':this_set['get_name']})
            else:
                logger.debug('No get_name provided: checking the set value using {}'.format(this_set['name']))
                get_kwargs.update({'endpoint':this_set['name']})
            result = self.interface.get(**get_kwargs)

            # choose to use the calibrated or raw value of the get value.
            if 'payload_field' in this_set:
                if 'value_cal' in result['payload'] and this_set['payload_field']=='value_cal':
                    value_get = result['payload']['value_cal']
                elif 'values' in result['payload'] and this_set['payload_field']=='values':
                    value_get = result['payload']['values'][0]
                elif 'value_raw' in result['payload'] and this_set['payload_field']=='value_raw':
                    value_get = result['payload']['value_raw']
                else:
                    raise dripline.core.DriplineInternalError('no payload matching!')
            else:
                if 'value_cal' in result['payload']:
                    value_get = result['payload']['value_cal']
                    logger.debug('no payload_field: using value_cal')
                elif 'values' in result['payload']:
                    value_get = result['payload']['values'][0]
                    logger.debug('no payload_field: using values')
                elif 'value_raw' in result['payload']:
                    value_get = result['payload']['value_raw']
                    logger.debug('no payload_field: using value_raw')

                else:
                    raise dripline.core.DriplineInternalError('no payload matching!')

            # sometimes the value get is in unicode (value_raw) -> switch to a readable value
            if isinstance(value_get, unicode):
                logger.debug('result in unicode -> formatting to utf-8')
                value_get = value_get.encode('utf-8')
            value_get_temp = value_get
            try:
                value_get = float(value_get_temp)
            except ValueError:
                logger.debug('value get ({}) is not floatable'.format(value_get))
                value_get = value_get_temp

            # checking a target has been given (else use the endpoint used to set)
            if 'target_value' in this_set:
                target_value = this_set['target_value']
            else:
                logger.debug('no target_value given: using value ({}) as a target_value to check'.format(this_set['value']))
                target_value = this_set['value']
            if value_get==None:
                raise dripline.core.DriplineValueError('value get is a None')

            # if the value we are checking is a float/int
            if isinstance(value_get, (int,float)):
                if not isinstance(target_value, (int,float)):
                    try:
                        target_value = float(target_value)
                    except ValueError:
                        logger.debug('target_value is not the same type as the value get: going to use the set value ({}) as target_value'.format(this_set['value']))
                        target_value = this_set['value']
                if isinstance(target_value, (int, float)):
                    if 'tolerance' in this_set:
                        tolerance = this_set['tolerance']
                    else:
                        tolerance = None
                    if tolerance==None:
                        logger.debug('No tolerance given: assigning an arbitrary tolerance (1.)')
                        tolerance = 1.
                    if not isinstance(tolerance, float) and not isinstance(tolerance, int) and not isinstance(tolerance, string_types):
                        logger.debug('tolerance is not a float or a string: assigning an arbitrary tolerance (1.)')
                        tolerance = 1.
                    if isinstance(tolerance, float) or isinstance(tolerance, int):
                        if tolerance == 0:
                            logger.debug('tolerance zero inacceptable: setting tolerance to 1.')
                            tolerance = 1.
                        if target_value -  tolerance <= value_get and value_get <= target_value + tolerance:
                            logger.debug('the value get ({}) is included in the target_value ({}) +- tolerance ({})'.format(value_get, target_value, tolerance))
                        else:
                            raise dripline.core.DriplineValueError('the value get ({}) is NOT included in the target_value ({}) +- tolerance ({}): stopping here!'.format(value_get, target_value, tolerance))
                    elif isinstance(tolerance, string_types):
                        if '%' not in tolerance:
                            tolerance = float(tolerance)
                        else:
                            match_number = re.compile('-?\ *[0-9]+\.?[0-9]*(?:[Ee]\ *-?\ *[0-9]+)?')
                            tolerance = [float(x) for x in re.findall(match_number, tolerance)][0] * target_value / 100.
                        if tolerance == 0:
                            logger.debug('tolerance zero inacceptable: setting tolerance to 1.')
                            tolerance = 1.
                        if target_value -  tolerance <= value_get and value_get <= target_value + tolerance:
                            logger.debug('the value get ({}) is included in the target_value ({}) +- tolerance ({})'.format(value_get, target_value, tolerance))
                        else:
                            raise dripline.core.DriplineValueError('the value get ({}) is NOT included in the target_value ({}) +- tolerance ({}): stopping here!'.format(value_get, target_value, tolerance))
                    else:
                        raise dripline.core.DriplineValueError('tolerance is not a float, int or string: stopping here')
                else:
                    raise dripline.core.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (float/int): stopping here!')

            # if the value we are checking is a string
            elif isinstance(value_get, string_types):
                if not isinstance(target_value, string_types):
                    logger.debug('target_value is not the same type as the value get: going to use the set value ({}) as target_value'.format(this_set['value']))
                    target_value==this_set['value']
                if isinstance(target_value, string_types):
                    target_value_backup = target_value
                    value_get_backup = value_get
                    # changing target_value in the dictionary
                    if target_value=='on' or target_value=='enable' or target_value=='enabled' or target_value=='positive':
                        target_value = '1'
                    if target_value=='off' or target_value=='disable' or target_value=='disabled' or target_value=='negative':
                        target_value = '0'
                    # changing value_get in the dictionary
                    if value_get=='on' or value_get=='enable' or value_get=='enabled' or value_get=='positive':
                        value_get = '1'
                    if value_get=='off' or value_get=='disable' or value_get=='disabled' or value_get=='negative':
                        value_get = '0'
                    # checking is target_value and value_get are the same
                    if target_value==value_get:
                        logger.debug('value get ({}) corresponds to the target_value ({}): going on'.format(value_get_backup, target_value_backup))
                    else:
                        raise dripline.core.DriplineValueError('value get ({}) DOES NOT correspond to the target_value ({}): stopping here!'.format(value_get_backup, target_value_backup))
                else:
                    raise dripline.core.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (string): stopping here!')

            # if the value we are checking is a bool
            elif isinstance(value_get, bool):
                if not isinstance(target_value, bool):
                    logger.debug('target_value is not the same type as the value get: going to use the set value ({}) as target_value'.format(this_set['value']))
                    target_value==this_set['value']
                if isinstance(target_value, bool):
                    if value_get==target_value:
                        logger.debug('value get ({}) corresponds to the target_value ({}): going on'.format(value_get, target_value))
                    else:
                        raise dripline.core.DriplineValueError('value get ({}) DOES NOT correspond to the target_value ({}): stopping here!'.format(value_get, target_value))
                else:
                    raise dripline.core.DriplineValueError('Cannot check! value set and target_value are not the same type as value get (string): stopping here!')

            # if you are in this "else", this means that you either wanted to mess up with us or you are not viligant enough
            else:
                raise dripline.core.DriplineValueError('value get ({}) is not a float, int, string, bool, None ({}): SUPER WEIRD!'.format(value_get, type(value_get)))

            logger.info('{} checked to {}'.format(this_set['name'], value_get))

    def action_do(self, operations, **kwargs):
        '''
        combine a set of set, cmd, and/or sleep actions as described above.
        This is included because it is helpful within multi_runs and adds no 
        new functionality at the top-level of a file, relative to the specifiction
        action types.

        Configfile entry::

            - action: do
              operations:
                - (sleep/sets/cmds):
                  A_VALID_OPERATIONS_LIST_OF_THIS_TYPE
                  ...
        '''
        logger.info('doing do block')
        for i_do,this_do in enumerate(operations):
            logger.info('doing operation #{}'.format(i_do))
            for key in this_do:
                if key == 'sets':
                    self.action_set(this_do[key])
                elif key == 'cmds':
                    self.action_cmd(this_do[key])
                elif key == 'sleep':
                    self.action_sleep(duration=this_do[key]['duration'])
                else:
                    logger.info('operation <{}> unknown: skipping!'.format(key))

    def action_esr_run(self, **kwargs):
        '''
        send a cmd run_scan to the esr service endpoint(esr_interface). The available
        arguments to send in the cmd are determined by the ESR service itself, but the most
        common/useful ones are
            config_instruments: (bool) configure lockin, sweeper, and relays (default: True)
            coils: (list) esr coils to use (default: [1,2,3,4,5])
            n_fits: (int) number of fits to attempt on ESR traces (default: 2)
        so it may be useful to include these in particular in run script file.

        Configfile entry::

            - action: esr_run
              timeout: (int||float) DURATION (default: )
              CMD_ARG: CMD_ARG_VALUE
              ...
        '''
        logger.info('Taking esr scan <esr_interface.run_scan> with args:\n{}'.format(kwargs))
        if self._dry_run_mode:
            logger.info('--dry-run flag: not starting an esr scan')
            return
        kwargs.update({'endpoint':'esr_interface',
                       'method_name':'run_scan'})
        # FIXME: method for passing warnings between esr service and run scripting to note that settings are being locked to defaults
        result = self.interface.cmd(**kwargs)
        # FIXME: ESR should run in background while sleep loops here pass
        logger.info(result['payload']['values'][0])

    # if available, this allows to record the trace/noise background on a daq.
    # this method depends on a method named "save_trace" defined in the associated daq class
    def action_single_trace(self, daq, trace, comment, timeout=None,**kwargs):
        '''
        collect the trace using one or more DAQ systems (if implemented).
        The trace corresponds to the instanteneous or cumulated fourier transform of the signal.
        The name given should be the absolute path for the daq to save the file.

        Configfile entry::

            - action: single_trace
              comment: COMMENT_STRING_TO_PASS_AS_REQUEST_KWARG
              daq: DAQ_ENDPOINT_NAME
              trace: TRACE_KWARG_TO_PASS_IN_DRIPLINE_REQUEST
              timeout: DRIPLINE_REQUEST_TIMEOUT
        '''
        logger.info('taking single trace')
        if self._dry_run_mode:
            logger.info('--dry-run flag: not starting an trace acquisition')
            return
        trace_kwargs = {'endpoint':daq,
                        'method_name':'save_trace',
                        'comment':comment,
                        'trace':trace,
                        'timeout': timeout
                       }
        if self._lockout_key:
            trace_kwargs.update({'lockout_key':self._lockout_key})
        logger.debug('trace_kwargs are: {}'.format(trace_kwargs))
        self.interface.cmd(**trace_kwargs)
        logger.debug('trace acquired')

    # take a single run using one or several daq.
    # this method depends on a method named "start_timed_run" defined in the associated daq class
    def action_single_run(self, daq_configs, run_name, timeout=None, **kwargs):
        '''
        collect a single run using one or more DAQ systems. The value provided
        for the run_duration currently must be number in seconds, it would be nice if
        in the future we could also accept strings that are mathematical expressions
        (so that you could do things like 2*60*60 to convert 2 hours to seconds, making
        it possible to represent the hours units with "*60*60" and keep the relevant 2).
        The run_name will be passed along to the start_timed_run method of each element
        of the daq_target list with .format(**{'name': <daq_target>}), allowing names
        of the form "shakedown of {}" to be parsed to "shakedown of NAME" or equivalent.

        Configfile entry::

            - action: single_run
              timeout: TIMEOUT_FOR_START_RUN_CMDS
              run_name: FORMATABLE_STRING_FOR_RUN_NAME
              daq_configs:
                - daq_target: DAQ_NAME
                  run_duration: TIME_IN_SECONDS
              ...
        '''
        logger.info('taking single run')
        if self._dry_run_mode:
            logger.info('--dry-run flag: not starting an electron run')
            return
        run_kwargs = {'endpoint':None,
                      'method_name':'start_timed_run',
                      'run_name':None,
                      'run_time':None
                     }

        if self._lockout_key:
            run_kwargs.update({'lockout_key':self._lockout_key})
        start_of_runs = datetime.datetime.now()
        max_duration = -1
        for item in daq_configs:
            run_kwargs.update({'endpoint':item['daq_target'],
                               'run_name':run_name.format(item['daq_target']),
                               'run_time':int(item['run_duration']),
                               'timeout': timeout})
            if run_kwargs['run_time'] > max_duration:
                max_duration = int(item['run_duration'])
            logger.debug('run_kwargs are: {}'.format(run_kwargs))
            result = self.interface.cmd(**run_kwargs)
            logger.info('{} started run {}'.format(item['daq_target'],result))
        logger.info('daq all started, now wait for requested livetime')
        logger.info('time remaining >= {:.0f} seconds'.format(max_duration-(datetime.datetime.now()-start_of_runs).total_seconds()))

        # Checking the status of the daq
        all_done = False
        a_daq_in_safe_mode = False
        while all_done is False:
            list_is_running = []
            for item in daq_configs:
                if self.interface.get(item['daq_target']+'._daq_in_safe_mode')['payload']['values'][0] is True:
                    logger.critical('{} is in safe_mode (maybe due to a set_condition)'.format(item['daq_target']))
                    a_daq_in_safe_mode = True
                if self.interface.get(item['daq_target']+'.is_running')['payload']['values'][0] is True:
                    list_is_running.append(item['daq_target'])
            if a_daq_in_safe_mode == True:
                if len(list_is_running)>0:
                    response = 'daq still running: '
                    for name in list_is_running:
                        response = response + '\n ' + name
                    logger.critical(response)
                logger.critical('Run scripting is stopping')
                sys.exit()
            duration = (datetime.datetime.now() - start_of_runs).total_seconds()
            if duration < max_duration:
                if len(list_is_running) == 0:
                    logger.critical('Run finished early! Expected remaining duration {}'\
                        .format(max_duration-(datetime.datetime.now()-start_of_runs).total_seconds()))
                    all_done = True
                else:
                    logger.info('time remaining >= {:.0f} seconds\n  still waiting on {}'\
                        .format(max_duration-(datetime.datetime.now()-start_of_runs).total_seconds(),list_is_running))
                    time.sleep(min(7*60,max(10,max_duration/14.)))
            else:
                if len(list_is_running) == 0:
                    all_done = True
                else:
                    logger.info('sleeping for 5 seconds\n  still waiting on {}'\
                        .format(list_is_running))
                    time.sleep(5)

        logger.info('acquistions complete')


    def action_multi_run(self, total_runs=None, operations=[], runs=None, **kwargs):
        '''
        probably the most useful/sophisticated action, effectively provides
        a for-loop structure. Each iteration will first go through any sets and/or cmds
        provided in operations, then collect a single run. The "value" field for sets will be modified in that
        it can be either a list, a dictionary or a string (it can also be a simple float/int).
        If it is a dictionary, a value will be expected to be indexable from the run_iterator
        (which starts at 0). If a string, then a value will be determiend using eval(VALUE.format(run_count)).
        Similarly, the run_name may contain both/either "{run_count}" or {daq_target}
        which will be passed as named replacements to format() (note that there will
        not be any un-named values to unpack). The run_duration may be a value (which
        will be used for all runs), or it may be an expression similar to the above
        sets (allowing for runs of variable duration). Note that for using esr scan in multi_run,
        one should give at least one field inside the esr_runs: for example, endpoint: esr_interface
        NOTE: in the runs block, a run_duration value will override the value provided in any particular
        daq config... this seems unintuitive but is what was done.
        NOTE: daq_targets is only considered if there is not a daq_configs entry... this seems unintuitive
        also. There is not an obviously good reason for this.

        Configfile entry::

            - action: multi_run
              operations: (default: [])
                VALID_DO_OPERATION_LIST
              esr_runs: (default:{})
                  VALID_ESR_RUN_BLOCK
              save_trace: (default: )
                  VALID_SAVE_TRACE_ACTION_BLOCK
              runs:
                  timeout: START_RUN_REQEUST_TIMEOUT
                  run_duration: {VALUE | "EXPRESSION" | {RUN_COUNT: VALUE, ...}}
                  run_name: STRING_OPTIONALLY_WITH_{daq_target}_AND/OR_{run_count}
                  daq_config:
                    - daq_targets: NAME
                      run_duration: RUN_DURATION_IN_SECONDS
                  daq_targets:
                    - DAQ_NAME
                    ...
              total_runs: NUMBER
        '''
        # kwargs will be checked for "esr_runs" dict, but otherwise ignored

        # establish default values for cache (in case of first call)
        # override with any values loaded from file
        # then update the instance variable with the current state
        logger.info("Starting action_multi_run with operations:\n{}".format(operations))
        initial_state = {'last_run': -1,}
        initial_state.update(self._action_cache)
        self._action_cache.update(initial_state)

        if not isinstance(total_runs, int):
            raise dripline.core.DriplineValueError("action_multi_run requires total_runs to be specified as int!")

        for run_count in range(total_runs):
            # skip runs that were already completed (only relevant if restarting an execution)
            logger.info('doing action [{}] run [{}]'.format(self._last_action+1, run_count))
            if run_count <= self._action_cache['last_run']:
                logger.info('run already complete, skipping')
                continue
            # compute args for, and call, action_set, based on run_count
            # for sets, we have to format/calculate the value to set using evaluator
            # this will build a new dictionary "evaluated_operations"
            # for cmds, we simply add them to the dictionary
            # then the evaluated_operations dictionary is procceded using the action_do()
            evaluated_operations = []
            for a_do in operations:
                key = list(a_do.keys())[0]
                # logger.info('doing operation #{}: {}'.format(i_do,key))
                if key == 'sets':
                    these_sets = []
                    for a_set in a_do[key]:
                        this_value = None
                        logger.info('set type is: {}'.format(type(a_set['value'])))
                        if isinstance(a_set['value'], (dict,list)) and isinstance(a_set['value'][run_count], (int,float,str,bool)):
                            this_value = a_set['value'][run_count]
                        elif isinstance(a_set['value'], (int,float,bool)):
                            this_value = a_set['value']
                        elif isinstance(a_set['value'], str):
                            if isinstance(self.evaluator(a_set['value'].format(run_count)), (int,float,str,bool)):
                                this_value = self.evaluator(a_set['value'].format(run_count))
                            elif isinstance(self.evaluator(a_set['value'].format(run_count)), list):
                                old_list = self.evaluator(a_set['value'].format(run_count))
                                new_list = []
                                for entry in old_list:
                                    if isinstance(entry,list):
                                        for subentry in entry:
                                            new_list.append(subentry)
                                    elif isinstance(entry, (int,float,str,bool)):
                                        new_list.append(entry)
                                    else:
                                        raise dripline.core.DriplineValueError('run_scripting does not support {}'.format(type(entry)))
                                this_value = new_list[run_count]
                            elif isinstance(self.evaluator(a_set['value'].format(run_count)), dict):
                                if isinstance(self.evaluator(a_set['value'].format(run_count))[run_count], (int,float,str,bool)):
                                    this_value = self.evaluator(a_set['value'].format(run_count))[run_count]
                                elif isinstance(self.evaluator(a_set['value'].format(run_count))[run_count], list):
                                    raise dripline.core.DriplineValueError('run_scripting does not support dict of lists')
                                else:
                                    raise dripline.core.DriplineValueError('rmissing value in the dict')

                        if this_value is None:
                            logger.info('failed to parse set:\n{}'.format(a_set))
                            raise dripline.core.DriplineValueError('Invalid set value!')
                        dict_temp = {'name': a_set['name'], 'value': this_value}
                        # these_sets.append({'name': a_set['name'], 'value': this_value})
                        for key in a_set:
                            if key != 'name' and key != 'value':
                                dict_temp.update({key: a_set[key]})
                        these_sets.append(dict_temp)
                    evaluated_operations.append({'sets':these_sets})
                elif key == 'cmds':
                    evaluated_operations.append({'cmds':a_do[key]})
                elif key == 'sleep':
                    evaluated_operations.append({'sleep':a_do[key]})
                elif key == 'Runs':
                    logger.debug('Runs should not be declared in the operations section: skipping!')
                else:
                    logger.debug('Operation unknown: skipping!')
            logger.debug('computed operations are:\n{}'.format(evaluated_operations))
            self.action_do(evaluated_operations)

            #ESR Scan
            if 'esr_runs' in kwargs:
                if not isinstance(kwargs['esr_runs'], dict):
                    kwargs['esr_runs'] = {}
                self.action_esr_run(**kwargs['esr_runs'])

            # compute args for, and call, action_single_run, based on run_count
            if 'save_trace' in kwargs:
                save_trace = kwargs['save_trace']
                this_trace_save_comment = save_trace['comment'].format(run_count=run_count)
                this_trace_number = save_trace['trace']
                if 'timeout' in save_trace:
                    this_timeout = save_trace['timeout']
                else:
                    this_timeout=None
                logger.debug('timeout set to {} s'.format(this_timeout))
                for this_daq in  save_trace['daq']:
                    logger.info('{} trace save will be on trace {} with name "{}"'.format(this_daq,this_trace_number, this_trace_save_comment))
                    self.action_single_trace(daq=this_daq, comment=this_trace_save_comment, trace = this_trace_number, timeout = this_timeout)

            # compute args for, and call, action_single_run, based on run_count
            if runs is not None:
                if 'timeout' in runs:
                    this_timeout = runs['timeout']
                else:
                    this_timeout=None
                logger.debug('timeout set to {} s'.format(this_timeout))

                # defining the run duration as a global variable is set in the 'run_duration'
                this_run_duration = None
                if 'run_duration' in runs:
                    if isinstance(runs['run_duration'], (float,int)):
                        this_run_duration = runs['run_duration']
                    elif isinstance(runs['run_duration'], (dict,list)):
                        this_run_duration = runs['run_duration'][run_count]
                    elif isinstance(runs['run_duration'], str):
                        this_run_duration = self.evaluator(runs['run_duration'].format(run_count))
                    else:
                        logger.info('failed to compute run duration for run: {}'.format(run_count))

                # this_run_duration = None
                daq_configs = []
                if 'daq_configs' in runs:
                    for a_daq_config in runs['daq_configs']:
                        # if isinstance(a_daq_config,str):
                        a_daq_target = a_daq_config['daq_target']
                        # elif isinstance(a_daq_config,dict):
                            # this_daq_target =a_daq_config['daq_target']
                        # else:
                        #     raise dripline.core.DriplineGenericDAQError('daq_target should be a list or a dict')
                        if this_run_duration is None:
                            a_run_duration = a_daq_config['run_duration']
                        else:
                            a_run_duration = this_run_duration
                    # daq_targets = runs['daq_config']
                        daq_configs.append({'daq_target': a_daq_target,
                                           'run_duration': a_run_duration})
                else:
                    for a_daq_target in runs['daq_targets']:
                        # if isinstance(a_daq_config,str):
                        # a_daq_target = a_daq_config
                        # elif isinstance(a_daq_config,dict):
                            # this_daq_target =a_daq_config['daq_target']
                        # else:
                        #     raise dripline.core.DriplineGenericDAQError('daq_target should be a list or a dict')
                        if this_run_duration is None:
                            raise dripline.core.DriplineGenericDAQError('run_duration must be given when using daq_targets list')
                        else:
                            a_run_duration = this_run_duration
                    # daq_targets = runs['daq_config']
                        daq_configs.append({'daq_target': a_daq_target,
                                           'run_duration': a_run_duration})
                this_run_name = runs['run_name'].format(daq_target='{}', run_count=run_count)
                self.action_single_run(daq_configs, this_run_name,this_timeout)


            # update cache variable with this run being complete and update the cache file
            self._action_cache['last_run'] = run_count
            self.update_cache()

    def do_unlocks(self):
        unlocked = []
        for target in self._to_unlock:
            result = self.interface.cmd(target, 'unlock', lockout_key=self._lockout_key)
            if result.retcode == 0:
                unlocked.append(target)
            else:
                logger.debug('unable to unlock <{}>'.format(target))
        for a_name in unlocked:
            self._to_unlock.remove(a_name)
