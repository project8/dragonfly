#!/usr/bin/python
'''
'''

import datetime
import logging
import multiprocessing
import time


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def slow_action(this_time):
    '''
    A dumb function that does some prints and sleeps to simulate something slow but useful.
    '''
    logger.info('.... will sleep for {}'.format(this_time))
    time.sleep(this_time)
    logger.info('.... slept for {}'.format(this_time))
    return this_time

# we want to allow subprocesses to exit gracefully, therefore we will subprocess in a subprocess so we can compute while we compute...
class slow_subprocess_mixin(object):
    '''
    Mix-in class for managing execution of workers in a subprocess.
    The default control function simply kills the workers, but a smarter version may be implemented/used instead.
    '''
    def __init__(self, worker_function, worker_args=(), worker_kwargs={}, control_function=None):
        '''
            control_function: reference to function to be run, it must have a kwarg 'halt_event' which is a multiprocessing.Event. When that event, the function is expected to exit in a timely but graceful fashion. Default=None. If none, use the provided slow_mixin.slow_target method, which will just execute the worker function and terminate() it when told to do so.
            worker_function: reference to function which actually does the desired work.
        '''
        if control_function is None:
            control_function = self.basic_control_target
        self._halt_event = multiprocessing.Event()
        top_kwargs = {'target': worker_function,
                      'args': worker_args,
                      'kwargs': worker_kwargs,
                      'halt_event': self._halt_event,
                     }
        self._control_process = multiprocessing.Process(target=control_function, kwargs=top_kwargs)

    @staticmethod
    def basic_control_target(halt_event, target, args=(), kwargs={}):
        '''
        A function which executes a worker function in a subprocess until either it returns, or a halt event is received.
        When the halt is set, the worker is terminated (the event is polled 10 times per second).
        There is no need to override this function as the __init__ allows another function name to be passed in (though override would work as well).

        halt_event (multiprocessing.Event): event to set() in order to force termination of the subprocess
        target (function): the function to call in the subprocess
        args (tuple): items to unpack as positional args to target
        kwargs (dict): items to unpack as kwargs to target
        '''
        if halt_event is None:
            halt_event = multiprocessing.Event()
        _worker_process = multiprocessing.Process(target=target, args=args, kwargs=kwargs)
        _worker_process.start()
        while (not halt_event.is_set()) and (_worker_process.is_alive()):
            time.sleep(0.1)
        logger.info("end of work/sleep loop")
        if _worker_process.is_alive():
            logger.debug('but worker still alive, terminate')
            _worker_process.terminate()

    def start_control_process(self):
        '''
        wrapper to call multiprocessing.Process.start()
        '''
        logger.info("starting a slow thing controller")
        self._control_process.start()

    def join_control_process(self, timeout=None):
        '''
        wrapper to call multiprocessing.Process.join(timeout=None)
        '''
        logger.debug("joining a slow thing")
        self._control_process.join(timeout)

    def control_process_is_running(self):
        '''
        wrapper to call multiprocessing.Process.is_alive()
        '''
        return self._control_process.is_alive()

    def stop_control_process(self, timeout=0):
        '''
        Signal the subprocess that it should terminate by setting the halt_event and then terminate it.

        timeout (int) [seconds]: number of seconds to allow the process to attempt to exit gracefully, after which terminate() is called if needed.
            Note that 0 seconds is valid and results in terminate being called immediately after the halt is set.
            Note that None is also valid and indicates that the process will be given unlimited time to exit cleanly. This method will join() the process and therefore blocks until the subprocess returns... Do this only with utmost caution
        '''
        logger.info('stopping a slow thing, it gets {} seconds to be graceful'.format(timeout))
        logger.debug("is it still running? -> {}".format(self.control_process_is_running()))
        self._halt_event.set()
        self._control_process.join(timeout)
        if self._control_process.exitcode is None:
            logger.debug("it didn't stop on its own, terminate")
            self._control_process.terminate()
        else:
            logger.debug("controller stopped on its own")

if __name__ == '__main__':
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    fmt = '%(asctime)s{}[%(levelname)-8s] %(name)s(%(lineno)d) -> {}%(message)s'
    try:
        import colorlog
        fmt = colorlog.ColoredFormatter(fmt.format('%(log_color)s', '%(purple)s'), datefmt='%Y-%m-%dT%H:%M:%S',reset=True)
    except ImportError:
        fmt = logging.Formatter(fmt.format(' ', ''), '%Y-%m-%dT%H:%M:%S')
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    sm = slow_subprocess_mixin(worker_function=slow_action, worker_args=(10,))
    logger.info("starting slow process: {}".format(datetime.datetime.now()))
    sm.start_control_process()
    logger.info('slow process is running -> {}'.format(sm.control_process_is_running()))
    sm.join_control_process(6)
    sm.stop_control_process(12)
    logger.info('process done: {}'.format(datetime.datetime.now()))
