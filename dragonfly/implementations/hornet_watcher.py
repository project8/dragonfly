import pyinotify, Queue, logging, os, re, ast

from dripline.core import fancy_doc

from subprocess_mixin import *

logger = logging.getLogger(__name__)

@fancy_doc
class HornetWatcher(SlowSubprocessMixin):

    def __init__(self, config, output_queue):
        '''
        A hornet watcher keeps staring at given directories and put file context to the output queue every time it notices a file close.
        config      : a dictionary contains a list of directories to be watched, a list of directories to be ignored, and the classification of different types of files (see example file for details).
        output_queue: a multiprocessing queue shared by hornet and the watcher.
        '''
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
                    logger.info(' I find a type for [' + path + ']: ' + t)
                    return rules['jobs']
            logger.warning(' I cannot classify [' + path + ']')
            return None

        def process_IN_CLOSE_WRITE(self, event):
            '''
            If the file being closed can be classified, do so and put the context into the queue.
            event: the pyinofity event detected.
            '''
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
                    self.output_queue.put_nowait(context)

    def watch(self):
        '''
        Start watching at specific directories and take action when noticing a file close.
        '''
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

