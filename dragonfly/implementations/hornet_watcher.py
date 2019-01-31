import pyinotify, Queue, logging, os, re, ast

import hornet

from subprocess_mixin import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class HornetWatcher(SlowSubprocessMixin):

    def __init__(self, config, output_queue):
        self.dirs = config['dirs']

        self.ignore_dirs = []
        if 'ignore-dirs' in config:
            self.ignore_dirs = config['ignore-dirs']
        
        self.types = config['types']
        for t in self.types:
            if t == '':
                logger.critical(' A type is missing its name.')
                os._exit(1)
            tests = 0
            if 'regexp' in self.types[t] and self.types[t]['regexp'] != '':
                regexp = self.types[t]['regexp']
                try:
                    re.compile(regexp)
                    tests += 1
                except re.error:
                    logger.critical(' Invalid regular expression: ' + regexp)
                    os._exit(1)
            if 'extension' in self.types[t] and self.types[t]['extension'] != '':
                tests += 1
            if tests < 1:
                logger.critical(' No tests provided for type ' + str(t))
                os._exit(1)

        self.output_queue = output_queue
        SlowSubprocessMixin.__init__(self, self.watch)
    
    class EventHandler(pyinotify.ProcessEvent):
        def __init__(self, dirs, ignore_dirs, types, output_queue):
            pyinotify.ProcessEvent.__init__(self)
            self.dirs = dirs
            self.ignore_dirs = ignore_dirs
            self.types = types
            self.output_queue = output_queue

        def find_jobs(self, path):
            file_name = os.path.basename(path)
            type_found = False
            for t in self.types:
                rules = self.types[t]
                if 'regexp' in rules:
                    pattern = re.compile(rules['regexp'])
                    type_found = pattern.match(file_name)
                if 'extension' in rules:
                    extension = rules['extension']
                    type_found = path.endswith(extension)
                if type_found:
                    logger.info(' I find a type for [' + path + ']: ' + t)
                    return rules['jobs']
            logger.warning(' I cannot classify [' + path + ']')
            return None

        def process_IN_CLOSE_WRITE(self, event):
            path = event.pathname
            for directory in self.ignore_dirs:
                if path.startswith(directory):
                    return
            logger.info(" File was closed with writing: " + path)
            for directory in self.dirs:
                if path.startswith(directory):
                    jobs = self.find_jobs(path)
                    if not jobs:
                        break
                    context = {}
                    context['path'] = path
                    context['jobs'] = jobs
                    logger.debug(context)
                    self.output_queue.put_nowait(str(context))

    def watch(self):
        wm = pyinotify.WatchManager()
        mask = pyinotify.IN_CLOSE_WRITE
        this_home = os.path.expanduser('~')
        for directory in self.dirs:
            absolute_path = os.path.join(this_home, directory)
            if os.path.exists(absolute_path):
                wm.add_watch(absolute_path, mask, rec=True)
                logger.info(' ' + absolute_path + ' is added to the watcher.')
            else:
                logger.error(' The directory ' +absolute_path + ' does not exist.')
        eh = self.EventHandler(self.dirs, self.ignore_dirs, self.types, self.output_queue)
        notifier = pyinotify.Notifier(wm, eh)
        notifier.loop()
