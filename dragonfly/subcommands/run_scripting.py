
'''
A parser which defines a syntax for writing run scripts. This should in principle
make it possible to define any data acquisition task (which might take hours or
even multiple days) in advance and have it proceed fully automatically. Furthermore,
"standard" run sets (such as calibrations) could be fully standardized and the same
run file used every time.

As with everything else, YAML will be the tested and preferred format for these files
(since json doesn't support comments), but json is expected to also work since
PyYAML can also parse that by default.

The file should parse to a list of dictionaries. Each dictionary will define a type of
action to take, in order, with various configurable parameters. Each will specify the
action with a line:

    action: {pause_for_user, lockout, set, single_run, multi_run}

pause_for_user -> print a message to the user and wait for a response. The content
    of the user's reply will not be stored or used. This allows indefinate pauses
    for user action. For example, changing the vertical position of the insert, which
    has to be done manually. Any result of the user action which needs to be measured
    should still be done automatically (using loggers, sets/cmds to endpoints, etc.)

        - action: pause_for_user
          message: STRING_TO_PRINT_PRIOR_TO_PAUSE

lockout -> send a lockout command to the specified list of endpoints. If a lockout
    action is called, all subsequent requests will use the automatically generated
    key. An unlock will automatically be called at the end of execution. For now,
    the only available configuration is the list of endpoints to lock:

        - action: lockout
          endpoints:
            - NAME
            - NAME
            ...

set -> send a list of set requests to change/ensure a desired system state. Initially
    these sets will be somewhat "blind" in the sense that they will only check the
    return code in the ReplyMessage, but will not further confirm that the system
    has achieved the requested state. The next iteration should add support for
    checking the returned value (assuming the endpoint has get_on_set == True) against
    the value requested, and allowing the user to specify some tolerance. A further
    enhancement would allow a similar check to be made by sending a "get" request
    to another endpoint (for example, set the current_limit of some power supply,
    then ensure that the current_output is close to the value desired). Both of
    these upgrades should be quite doable, but significantly increase the edge cases
    that must be considered:

        - action: set
          sets:
            - name: NAME
              value: VALUE
            - name: NAME
              value: VALUE
            ...

single_run -> collect a single run using one or more DAQ systems. The value provided
    for the run_duration currently must be number in seconds, it would be nice if
    in the future we could also accept strings that are mathematical expressions
    (so that you could do things like 2*60*60 to convert 2 hours to seconds, making
    it possible to represent the hours units with "*60*60" and keep the relevant 2).
    The run_name will be passed along to the start_timed_run method of each element
    of the daq_target list with .format(**{'name': <daq_target>}), allowing names
    of the form "shakedown of {}" to be parsed to "shakedown of NAME" or equivalent.

        - action: single_run
          run_duration: TIME_IN_SECONDS
          run_name: STRING_FOR_RUN_NAME
          daq_targets:
            - NAME
            - NAME
          ...

multi_run -> probably the most useful/sophisticated action, effectively provides
    a for-loop structure. Each iteration will first go through any provided sets,
    then collect a single run. The "value" field for sets will be modified in that
    it can be either dictionary or a string. If it is a dictionary, a vale will
    be expected to be indexable from the run_iterator (which starts at 0). If a
    string, then a value will be determiend using eval(VALUE.format(run_count)).
    Similarly, the run_name may contain both/either "{run_count}" or {daq_target}
    which will be passed as named replacements to format() (note that there will
    not be any un-named values to unpack). The run_duration may be a value (which
    will be used for all runs), or it may be an expression similar to the above
    sets (allowing for runs of variable duration).

      - action: multi_run
        sets:
          - name: NAME
            value:
              0: VALUE
              1: VALUE
              2: VALUE
          - name: NAME
            value: "EXPRESION*{}"
          ...

        runs:
            run_duration: {VALUE | "EXPRESSION" | {RUN_COUNT: VALUE, ...}}
            run_name: STRING_OPTIONALLY_WITH_{daq_target}_AND/OR_{run_count}
            daq_targets:
              - NAME
              - NAME
        total_runs: VALUE
'''

from __future__ import absolute_import

import datetime
import json
import logging
import time
import uuid

import asteval
import yaml

import dripline

logger = logging.getLogger(__name__)

__all__ = []

__all__.append('RunScript')
class RunScript(object):
    '''
    use configuration file to configure system state and take data
    '''
    name = 'execute'

    def __init__(self, *args, **kwargs):
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
        self._cache_file_name = '/tmp/execution_cache.json'
        self.interface = None

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
            # file doesn't exit assume starting from the beginning
            pass

    def update_parser(self, parser):
        parser.add_argument('execution_file',
                            help='file containing the detailed execution steps',
                           )

    def __call__(self, kwargs):
        if not 'broker' in kwargs:
            kwargs.broker = 'localhost'
        if kwargs.broker is None:
            kwargs.broker = 'localhost'
        # create interface
        self.interface = dripline.core.Interface(amqp_url=kwargs.broker, name='execution_script')
        # update self from cache file
        self.update_from_cache_file()
        try:
            # do each of the actions listed in the execution file
            actions = yaml.load(open(kwargs.execution_file))
            if self._last_action == len(actions)-1:
                logger.warning('cache file indicates this execution is already complete')
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
                    logger.warning('action <{}> not supported, perhaps your execution file has a typo?'.format(method_name.replace('action_','')))
                    raise dripline.core.DriplineMethodNotSupportedError('RunScript class has no method <{}>'.format(method_name))
                this_method(**action)
                self._last_action = i_action
                self._action_cache = {}
                self.update_cache()
        # finally, unlock anything we locked (even if there's an exception along the way)
        finally:
            if self._lockout_key is not None:
                self.do_unlocks()
        logger.info('execution complete')

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
        # note, this is python2 specific... (in python3 it is input not raw_input
        # but python2 has something different named input
        raw_input('{}\n(Press return to continue)\n'.format(message))

    def action_lockout(self, endpoints=[], lockout_key=None, **kwargs):
        if lockout_key is not None:
            self._lockout_key = lockout_key
        if self._lockout_key is None:
            self._lockout_key = uuid.uuid4().get_hex()
        logger.info('locking with key: {}'.format(self._lockout_key))
        logger.info('endpoings are: {}'.format(endpoints))
        for target in endpoints:
            result = self.interface.cmd(target, 'lock', lockout_key=self._lockout_key)
            if result.retcode == 0:
                if target not in self._to_unlock:
                    self._to_unlock.append(target)
            else:
                logger.warning('unable to lock <{}>'.format(target))
                raise dripline.core.exception_map[result.retcode](result.return_msg)

    def action_set(self, sets, **kwargs):
        logger.info('doing set block')
        set_kwargs = {'endpoint':None, 'value':None}
        if self._lockout_key:
            set_kwargs.update({'lockout_key':self._lockout_key})
        for this_set in sets:
            set_kwargs.update({'endpoint':this_set['name'],'value':this_set['value']})
            result = self.interface.set(**set_kwargs)
            if result.retcode == 0:
                logger.debug('...set of {}->{} complete'.format(this_set['name'], this_set['value']))
            else:
                logger.warning('unable to set <{}>'.format(this_set['name']))
                raise dripline.core.exception_map[result.retcode](result.return_msg)

    def action_single_run(self, run_duration, run_name, daq_targets, **kwargs):
        logger.info('taking single run')
        run_kwargs = {'endpoint':None,
                      'method_name':'start_timed_run',
                      'run_name':None,
                      'run_time':run_duration,
                     }
        if self._lockout_key:
            run_kwargs.update({'lockout_key':self._lockout_key})
        start_of_runs = datetime.datetime.now()
        for daq in daq_targets:
            run_kwargs.update({'endpoint':daq, 'run_name':run_name.format(daq)})
            logger.debug('run_kwargs are: {}'.format(run_kwargs))
            self.interface.cmd(**run_kwargs)
        logger.info('daq all started, now wait for requested livetime')
        while (datetime.datetime.now() - start_of_runs).total_seconds() < run_duration:
            logger.info('time remaining >= {:.0f} seconds'.format(run_duration-(datetime.datetime.now()-start_of_runs).total_seconds()))
            time.sleep(5)
        all_done = False
        logger.info('ideal livetime over, waiting for daq systems to finish')
        while all_done == False:
            all_done = True
            for daq in daq_targets:
                if self.interface.get(daq+'.is_running')['payload']['values'][0]:
                    all_done = False
                    logger.info('still waiting on <{}> (maybe others)'.format(daq))
                    break
            time.sleep(5)
        logger.info('acquistions complete')

    def action_multi_run(self, runs, total_runs, sets=[], **kwargs):
        # establish default values for cache (in case of first call)
        # override with any values loaded from file
        # then update the instance variable with the current state
        initial_state = {'last_run': -1,}
        initial_state.update(self._action_cache)
        self._action_cache.update(initial_state)

        for run_count in range(total_runs):
            # skip runs that were already completed (only relevant if restarting an execution)
            logger.info('doing action [{}] run [{}]'.format(self._last_action+1, run_count))
            if run_count <= self._action_cache['last_run']:
                logger.info('run already complete, skipping')
                continue
            # compute args for, and call, action_set, based on run_count
            these_sets = []
            evaluator = asteval.Interpreter()
            for a_set in sets:
                this_value = None
                logger.info('set type is: {}'.format(type(a_set['value'])))
                if isinstance(a_set['value'], dict):
                    this_value = a_set['value'][run_count]
                elif isinstance(a_set['value'], str):
                    this_value = evaluator(a_set['value'].format(run_count))
                else:
                    logger.info('failed to parse set:\n{}'.format(a_set))
                    raise dripline.core.DriplineValueError('set value not a dictionary or evaluatable expression')
                these_sets.append({'name': a_set['name'], 'value': this_value})
            logger.info('computed sets are:\n{}'.format(these_sets))
            self.action_set(these_sets)
            # compute args for, and call, action_single_run, based on run_count
            this_run_duration = None
            if isinstance(runs['run_duration'], float) or isinstance(runs['run_duration'], int):
                this_run_duration = runs['run_duration']
            elif isinstance(runs['run_duration'], dict):
                this_run_duration = runs['run_duration'][run_count]
            elif isinstance(runs['run_duration'], str):
                this_run_duration = evaluator(runs['run_duration'].format(run_count))
            else:
                logger.info('failed to compute run duration for run: {}'.format(run_count))
                raise dripline.core.DriplineValueError('set value not a dictionary or evaluatable expression')
            this_run_name = runs['run_name'].format(daq_target='{}', run_count=run_count)
            logger.info('run will be [{}] seconds with name "{}"'.format(this_run_duration, this_run_name))
            self.action_single_run(this_run_duration, this_run_name, runs['daq_targets'])
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
                logger.warning('unable to unlock <{}>'.format(target))
        for a_name in unlocked:
            self._to_unlock.remove(a_name)
