from __future__ import absolute_import

import logging, os, datetime, time, multiprocessing, sys
import yaml

from .hornet_watcher import HornetWatcher
from .hornet_mover import HornetMover

from dripline.core import Endpoint, fancy_doc

from .subprocess_mixin import SlowSubprocessMixin

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
        '''
        Hornet watches for file close events in certain directories, and process files based on their classifications.
        process_interval: the time interval between two file processing.
        watcher_config  : a dictionaty containing a list of directories to watch, a list of directories to ignore, and a dictionary conatining different classifications for files (see example yaml file for details).
        modules         : a dictionary containing hornet modules, and each module should contain an instance method run().
        '''
        self.process_interval = datetime.timedelta(**process_interval)
        self.watcher_config = watcher_config
        self.modules = modules
        Endpoint.__init__(self, **kwargs)
        SlowSubprocessMixin.__init__(self, self.run)

    def process_files(self, watcher_output_queue, modules):
        '''
        Get files and their jobs to do from the given queue and process them one by one.
        watcher_output_queue: the queue shared between hornet and its watcher that contains file information. Each file context retrieved from the queue contains the absolute path of the file, and its job to do.
        modules             : a dictionary contains all the instances of modules - each of them should contain a run() method, which takes the file path as parameter and also return a path.
        '''
        logger.info(' I am ready to process files!')
        watcher_count = 0
        try:
            while not watcher_output_queue.empty():
                watcher_count += 1
                context = watcher_output_queue.get_nowait()
                path = context['path']
                jobs = context['jobs']
                logger.debug('I have found jobs ' + str(jobs) + ' for ' + path)
                for job in jobs:
                    logger.debug('I am sending the file to the ' + job)
                    path = modules[job].run(path)
            logger.info("Finish processing files. Sending an alert message.")
            message = 'I have processed ' + str(watcher_count) + ' item(s).'
            severity = 'status_message.{}.{}'.format("notice", self.service.name)
            self.service.send_alert(severity=severity, alert=message)
        except Exception, e: # just in case
            logger.error(e)

    def run(self):
        '''
        It processes files on a regular basis.
        '''
        logger.info('Setting up the watcher')
        watcher_output_queue = multiprocessing.Queue()
        watcher = HornetWatcher(self.watcher_config, watcher_output_queue)
        
        modules = {}
        for module in self.modules:
            module_config = self.modules[module]
            logger.info('Setting up the ' + module)
            logger.debug(module_config)
            hornet_class = getattr(sys.modules[__name__], module_config['module'])
            modules[module] = hornet_class(**module_config)
  
        watcher.start_control_process()
        logger.info('Start to process existing files first.')
        self.process_files(watcher_output_queue, modules)
        process_time = datetime.datetime.now() + self.process_interval
        logger.info('I will start at ' + str(process_time))
        
        try:
            while True:
                if (datetime.datetime.now() > process_time):
                    self.process_files(watcher_output_queue, modules)
                    process_time = datetime.datetime.now() + self.process_interval
                    logger.info(' I will be working again at ' + str(process_time))
        finally:
            logger.info('I am being terminated. Trying to close the watcher...')
            watcher.join_control_process()
            logger.info('The watcher has been closed. See you next time!')
            os._exit(0)
