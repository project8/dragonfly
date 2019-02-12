import datetime
import logging
import multiprocessing
import time

__all__ = []

logger = logging.getLogger(__name__)

# dumb slow function for testing purposes
def slow_action(this_time):
    '''
    A dumb function that does some prints and sleeps to simulate something slow but useful.
    '''
    '''
    logger.info('.... will sleep for {}'.format(this_time))
    time.sleep(this_time)
    logger.info('.... slept for {}'.format(this_time))
    return this_time
    '''
    while True:
        print (str(datetime.datetime.now()))
        time.sleep(1)
__all__.append('SlowSubprocessMixin')
class SlowSubprocessMixin(object):
    def __init__(self, worker_function, worker_args=(), worker_kwargs={}, control_function=None):

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
        logger.info("starting a slow thing controller")
        self._control_process.start()

    def join_control_process(self, timeout=None):
        logger.debug("joining a slow thing")
        self._control_process.join(timeout)

    def control_process_is_running(self):
        return self._control_process.is_alive()

    def stop_control_process(self, timeout=0):
        logger.info('stopping a slow thing, it gets {} seconds to be graceful'.format(timeout))
        logger.debug("is it still running? -> {}".format(self.control_process_is_running()))
        self._halt_event.set()
        self._control_process.join(timeout)
        if self._control_process.exitcode is None:
            logger.debug("it didn't stop on its own, terminate")
            self._control_process.terminate()
        else:
            logger.debug("controller stopped on its own")


# testing... should probably move this into real unit tests
if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
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

    sm = SlowSubprocessMixin(worker_function=slow_action, worker_args=(10,))
    logger.info("starting slow process: {}".format(datetime.datetime.now()))
    sm.start_control_process()
    logger.info('slow process is running -> {}'.format(sm.control_process_is_running()))
    time.sleep(10)
    sm.join_control_process(6)
    sm.stop_control_process(12)
    logger.info('process done: {}'.format(datetime.datetime.now()))
    
