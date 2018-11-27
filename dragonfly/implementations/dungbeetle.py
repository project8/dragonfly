import os, datetime, logging

from dripline.core import Endpoint, Scheduler, fancy_doc

logger = logging.getLogger(__name__)


__all__ = []
__all__.append('DungBeetle')
@fancy_doc
class DungBeetle(Endpoint,Scheduler):
    '''
    A scheduler endpoint for removing stale directories.
    '''
    def __init__(self,
                 root_dirs = [],
                 max_age = {"hours":2},
                 ignore_dirs = [],
                 warning_interval = 12,
                 **kwargs):
        '''
        root_dirs (list of str): list of strings naming paths to monitor, these dirs are not removed
        max_age (dict): min age for a directory to be removed if empty, is a dict of kwargs to datetime.timedelta.__init__
        ignore_dirs (list of str): list of string names of paths to ignore, each must be a full path (starting with the corresponding value from root_dirs)
        warning_interval (int): the number of cycles that a warning will be sent when a directory has not been removed for a long time
        '''
        Endpoint.__init__(self, **kwargs)
        Scheduler.__init__(self, **kwargs)

        self.root_dirs = root_dirs
        self.max_age = datetime.timedelta(**max_age)
        self.ignore_dirs = ignore_dirs
        self.processed_dirs = {}
        self.warning_interval = warning_interval

    # recursively delete empty directories
    def del_dir(self, path, min_creation_time, processed_dirs_per_cycle, new_dirs):
        if os.path.isdir(path):
            creation_time = datetime.datetime.fromtimestamp(os.path.getctime(path))
            no_sub_dir = True
            for item in os.listdir(path):
                sub_path = os.path.join(path, item)
                no_sub_dir = no_sub_dir and (not os.path.isdir(sub_path))
                self.del_dir(sub_path, min_creation_time, processed_dirs_per_cycle, new_dirs)
            if creation_time < min_creation_time and (not path in self.ignore_dirs):
                try:
                    os.rmdir(path)
                    logger.info(" path [{}] has been removed.".format(path))
                except OSError, err:
                    if no_sub_dir:
                        processed_dirs_per_cycle.append(path)
                        if path not in self.processed_dirs:
                            self.processed_dirs[path] = 1
                            new_dirs.append(path)
                        else:
                            self.processed_dirs[path] += 1

    # clean up empty directories under a specific directory without deleting itself
    def clean_dir(self, processed_dirs_per_cycle, new_dirs):
        logger.debug(" going to clean directories")
        min_creation_time = datetime.datetime.now() - self.max_age
        for root_dir in self.root_dirs:
            logger.debug(" checking {}".format(root_dir))
            if os.path.isdir(root_dir):
                for item in os.listdir(root_dir):
                    sub_path = os.path.join(root_dir, item)
                    self.del_dir(sub_path, min_creation_time, processed_dirs_per_cycle, new_dirs)
            else:
                raise Exception(" path [{}] does not exist.".format(root_dir))

    def scheduled_action(self):
        logger.info(" doing scheduled check")
        processed_dirs_per_cycle = []
        new_warning_list = []
        old_warning_list = []
        self.clean_dir(processed_dirs_per_cycle, new_warning_list)
        for directory in list(self.processed_dirs):
            if directory not in processed_dirs_per_cycle:
                del self.processed_dirs[directory]
            elif self.processed_dirs[directory]  > 1 and self.processed_dirs[directory ]% self.warning_interval == 1:
                old_warning_list.append(directory)
        message = ''
        new_list_length = len(new_warning_list)
        old_list_length = len(old_warning_list)
        if new_list_length > 0:
            message += ' ' + str(new_list_length) + ' new path(s) not removed because not empty: {}'.format(new_warning_list) + '\n'
        if old_list_length > 0:
            message += ' ' + str(old_list_length) + ' old path(s) not removed for more than ' + str(self.warning_interval) + ' cycles: {}'.format(old_warning_list) + '\n'
        if message != '':
            logger.warning(message)
            
