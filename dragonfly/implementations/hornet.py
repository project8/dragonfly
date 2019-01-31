import logging, os, Queue, datetime, yaml, time, multiprocessing, sys, ast

from hornet_watcher import *
from hornet_mover import *
from hornet_printer import *

from subprocess_mixin import *

logger = logging.getLogger(__name__)

class Hornet(SlowSubprocessMixin):
    
    def __init__(self, 
                 process_interval,
                 watcher_config,
                 modules,
                 **kwargs):
        
        self.process_interval = datetime.timedelta(**process_interval)
        self.watcher_config = watcher_config
        self.modules = modules
        SlowSubprocessMixin.__init__(self, self.run)

    def run(self):

        logger.info(' Setting up the watcher')
        manager = multiprocessing.Manager()
        watcher_output_queue = manager.Queue()
        watcher = HornetWatcher(self.watcher_config, watcher_output_queue)
        
        modules = {}
        for module in self.modules:
            module_config = self.modules[module]
            logger.info(' Setting up the ' + module)
            logger.debug(module_config)
            hornet_class = getattr(sys.modules[__name__], module_config['module'])
            modules[module] = hornet_class(**module_config)
  
        watcher.start_control_process()
        process_time = datetime.datetime.now() + self.process_interval

        while True:
            if (datetime.datetime.now() > process_time):
                watcher_count = 0
                while not watcher_output_queue.empty():
                    watcher_count += 1
                    context = ast.literal_eval(watcher_output_queue.get())
                    logger.debug(' Here is the info I get from the watcher: ' + str(context))
                    path = context['path']
                    jobs = context['jobs']
                    logger.debug(' I have found jobs ' + str(jobs) + ' for ' + path)
                    for job in jobs:
                        path = modules[job].run(path)
                logger.info(' I have processed ' + str(watcher_count) + ' item(s) .')
                process_time = datetime.datetime.now() + self.process_interval

        # how to reach here?
        logger.info(' I am closing the watcher.')
        watcher.stop_control_process(10)
