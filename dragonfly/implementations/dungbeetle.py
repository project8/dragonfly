import os, datetime, logging

from dripline.core import Endpoint, Scheduler, fancy_doc

__all__ = []
__all__.append('DungBeetle')
@fancy_doc
class DungBeetle(Endpoint,Scheduler):
    def __init__(self,
                 root_dirs = [],
                 max_age = {"hours":2},
                 ignore_dirs = [],
                 **kwargs):
        '''
        root_dirs (list of str): list of strings naming paths to monitor, these dirs are not removed
        max_age (dict): min age for a directory to be removed if empty, is a dict of kwargs to datetime.timedelta.__init__
        ignore_dirs (list of str): list of string names of paths to ignore, each must be a full path (starting with the corresponding value from root_dirs)
        '''
        Endpoint.__init__(self, **kwargs)
        Scheduler.__init__(self, **kwargs)
        
        self.root_dirs = root_dirs
        self.max_age = datetime.timedelta(**max_age)
        self.ignore_dirs = ignore_dirs

    # recursively delete empty directories
    def del_dir(self, path, min_creation_time):
        if os.path.isdir(path):
            creation_time = datetime.datetime.fromtimestamp(os.path.getctime(path))
            for item in os.listdir(path):
                sub_path = os.path.join(path, item)
                self.del_dir(sub_path, min_creation_time)
            if creation_time < min_creation_time and (not path in self.ignore_dirs):
                try:
                    os.rmdir(path)
                    logging.info(" path [{}] has been removed.".format(path))
                except OSError, err:
                    logging.warn(" path [{}] not removed because not empty".format(path))

    # clean up empty directories under a specific directory without deleting itself
    def clean_dir(self):
        min_creation_time = datetime.datetime.now() - self.max_age
	for root_dir in self.root_dirs:
            if os.path.isdir(root_dir):
                for item in os.listdir(root_dir):
                    sub_path = os.path.join(root_dir, item)
                    self.del_dir(sub_path, min_creation_time)
            else:
                raise Exception(" path [{}] does not exist.".format(root_dir))    
   
    def scheduled_action(self):
        self.clean_dir()
        
