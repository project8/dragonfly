from __future__ import absolute_import

try:
    import pyinotify
except ImportError:
    pass

import Queue, logging, os, re, ast

from dripline.core import fancy_doc

from .subprocess_mixin import SlowSubprocessMixin


__all__ = []
__all__.append('HornetWatcher')

logger = logging.getLogger(__name__)

@fancy_doc
class HornetWatcher(SlowSubprocessMixin):

    def __init__(self, config, output_queue):
        '''
        A hornet watcher keeps staring at given directories and put file context to the output queue every time it notices a file close.
        config      : a dictionary contains a list of directories to be watched, a list of directories to be ignored, and the classification of different types of files (see example file for details).
        output_queue: a multiprocessing queue shared by hornet and the watcher.
        '''
        if 'pyinotify' not in globals():
            raise ImportError('pyinotify not found, required for HornetWatcher class.')
            
        this_home = os.path.expanduser('~')
        self.dirs = []
        for directory in config['dirs']:
            self.dirs.append(os.path.join(this_home, directory))
        self.ignore_dirs = []
        for directory in config['ignore-dirs']:
            self.ignore_dirs.append(os.path.join(this_home, directory))
        
        self.types = config['types']
        for t in self.types:
            if t == '':
                logger.critical('A type is missing its name.')
                os._exit(1)
            tests = 0
            if 'regexp' in self.types[t] and self.types[t]['regexp'] != '':
                regexp = self.types[t]['regexp']
                try:
                    re.compile(regexp)
                    tests += 1
                except re.error:
                    logger.critical('Invalid regular expression: ' + regexp)
                    os._exit(1)
            if 'extension' in self.types[t] and self.types[t]['extension'] != '':
                tests += 1
            if tests < 1:
                logger.critical('No tests provided for type ' + str(t))
                os._exit(1)

        self.output_queue = output_queue
        SlowSubprocessMixin.__init__(self, self.watch)
    
    class EventHandler(pyinotify.ProcessEvent):
        def __init__(self, dirs, ignore_dirs, types, output_queue):
            '''
            The event handler is responsible for classifying the file.
            dirs        : a list of directories being watched.
            ignore_dirs : a list of directories being ignored.
            types       : a list of dictionaries containing the regular expression/extension and jobs to do for each type of files.
            output_queue: the multiprocessing queue shared by hornet and the watcher.
            '''
            pyinotify.ProcessEvent.__init__(self)
            self.dirs = dirs
            self.ignore_dirs = ignore_dirs
            self.types = types
            self.output_queue = output_queue

        def find_jobs(self, path):
            '''
            Returns a list of jobs to do for the given file.
            path: the absolute path of the file to be classified.
            '''
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
                    logger.debug('I find a type for [' + path + ']: ' + t)
                    return rules['jobs']
            logger.warning('I cannot classify [' + path + ']')
            return None

        def process_IN_CLOSE_WRITE(self, event):
            '''
            If the file being closed can be classified, do so and put the context into the queue.
            event: the pyinofity event detected.
            '''
            logger.debug("A file close event is detected. Should it be ignored?")
            path = event.pathname
            for directory in self.ignore_dirs:
                if path.startswith(directory):
                    return
            logger.debug("File was closed with writing: " + path)
            for directory in self.dirs:
                if path.startswith(directory):
                    jobs = self.find_jobs(path)
                    if not jobs:
                        break
                    context = {}
                    context['path'] = path
                    context['jobs'] = jobs
                    logger.debug(context)
                    self.output_queue.put_nowait(context)

    def watch(self):
        '''
        Start watching at specific directories and take action when noticing a file close.
        '''
        wm = pyinotify.WatchManager()
        mask = pyinotify.IN_CLOSE_WRITE
        for directory in self.dirs:
            if os.path.exists(directory):
                wm.add_watch(directory, mask, rec=True)
                logger.info(directory + ' is added to the watcher.')
            else:
                logger.error('The directory ' + directory + ' does not exist.')
        eh = self.EventHandler(self.dirs, self.ignore_dirs, self.types, self.output_queue)
        notifier = pyinotify.Notifier(wm, eh)
        notifier.loop()
