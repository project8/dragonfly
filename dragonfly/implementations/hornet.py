import logging, os, datetime, yaml, time, multiprocessing, sys

from hornet_watcher import *
from hornet_mover import *
from hornet_printer import *

from dripline.core import Endpoint, fancy_doc

from subprocess_mixin import *

__all__ = []
__all__.append('Hornet')

logger = logging.getLogger(__name__)

@fancy_doc
class Hornet(SlowSubprocessMixin, Endpoint):
    
    def __init__(self, 
                 process_interval,
                 watcher_config,
                 modules,
                 **kwargs):
        
        self.process_interval = datetime.timedelta(**process_interval)
        self.watcher_config = watcher_config
        self.modules = modules
        Endpoint.__init__(self, **kwargs)
        SlowSubprocessMixin.__init__(self, self.run)

    def process_files(self, watcher_output_queue, modules):
        logger.info(' I am ready to process files!')
        watcher_count = 0
        try:
            while not watcher_output_queue.empty():
                watcher_count += 1
                context = watcher_output_queue.get_nowait()
                path = context['path']
                jobs = context['jobs']
                logger.debug(' I have found jobs ' + str(jobs) + ' for ' + path)
                for job in jobs:
                    logger.debug(' I am sending the file to the ' + job)
                    path = modules[job].run(path)
            logger.info(' I have processed ' + str(watcher_count) + ' item(s) .')
        except IOError:
            print('that is sad')


    def run(self):

        logger.info(' Setting up the watcher')
        watcher_output_queue = multiprocessing.Queue()
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
        logger.info(' I will start at ' + str(process_time))

        while True:
            try:
                if (datetime.datetime.now() > process_time):
                    self.process_files(watcher_output_queue, modules)
                    process_time = datetime.datetime.now() + self.process_interval
                    logger.info(' I will be working again at ' + str(process_time))
            except KeyboardInterrupt:
                logger.info(' I am being terminated. Trying to finish remaining work first...')
                watcher.join_control_process()
                self.process_files(watcher_output_queue, modules)
                print(watcher_output_queue)
                logger.info(' The watcher has been closed. See you next time!')
                os._exit(0)
                






