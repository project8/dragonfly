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

    action: {lockout, set, single_run, multi_run}

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
    Similarly, the run_name may contain both/either '{run_count}' or '{daq_target}'
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
            run_name: "STRING_OPTIONALLY_WITH_{daq_target}_AND/OR_{run_count}"
            daq_targets:
              - NAME
              - NAME
'''
## TODO items:
#  ~ various enhancements from each of the action descriptions above
#  ~ /tmp file to cache state and recover aborted/crashed execution


from __future__ import absolute_import

import logging
import uuid

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

    def __init__(self, broker='localhost', **kwargs):
        for kwarg in kwargs:
            logger.warning('got unexpected kwarg: <{}>:<{}>'.format(kwarg, kwargs[kwarg]))
        self._lockout_key = None
        self.__to_unlock = []
        self.interface = dripline.core.Interface(amqp_url=broker, name='execution_script')

    def __call__(self, kwargs):
        # do each of the actions listed in the execution file
        # finally, unlock anything we locked
        if self._lockout_key is not None:
            self.do_unlocks()

    def update_parser(self, parser):
        parser.add_argument('execution_file',
                            help='file containing the detailed execution steps'
                           )

    def action_lockout(self, endpoints=[], **kwargs):
        self._lockout_key = uuid.uuid4().get_hex()
        for target in endpoints:
            result = self.interface.cmd(target, 'lock', key=self._lockout_key)
            if result.retcode == 0:
                self.__to_unlock.append(target)
            else:
                logger.warning('unable to lock <{}>'.format(target))
                raise dripline.core.exception_map[result.retcode](result.return_msg)

    def action_set(self, sets, **kwargs):
        set_kwargs = {target:None, value:None}
        if self._lockout_key:
            set_kwargs.update({'key':self._lockout_key})
        for target,value in sets.items():
            result = self.interface.set(**set_kwargs)
            if result.retcode == 0:
                logger.info('set of {}->{} complete'.format(target, value))
            else:
                logger.warning('unable to set <{}>'.format(target))
                raise dripline.core.exception_map[result.retcode](result.return_msg)
        
    def action_single_run(self, **kwargs):
        pass
    def action_multi_run(self, **kwargs):
        pass

    def do_unlocks(self):
        unlocked = []
        for target in self.__to_unlock:
            result = self.interface.cmd(target, 'unlock', key=self._lockout_key)
            if result.retcode == 0:
                unlocked.append(target)
            else:
                logger.warning('unable to unlock <{}>'.format(target))
        for a_name in unlocked:
            self.__to_unlock.remove(a_name)
