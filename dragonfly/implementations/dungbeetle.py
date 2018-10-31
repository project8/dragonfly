import os, datetime, logging

from dripline.core import Endpoint, Scheduler, fancy_doc

__all__ = []
__all__.append('DungBeetle')
@fancy_doc
class DungBeetle(Endpoint,Scheduler):

    def __init__(self, root_dirs = [], max_age = "2h", ignore_dirs = [], **kwargs):
        Endpoint.__init__(self, **kwargs)
        Scheduler.__init__(self, **kwargs)
        
        self.root_dirs = root_dirs
        self.max_age = max_age
        self.ignore_dirs = ignore_dirs

    # convert a string representing time to seconds
    def get_seconds(self, time):
	units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
	seconds = 0
	for s in time.split('/'):
	    seconds += int(s[:-1]) * units[s[-1]]
        return seconds

    # recursively delete empty directories
    def del_dir(self, path, min_ctime):
        if os.path.isdir(path):
            ctime = datetime.datetime.fromtimestamp(os.path.getctime(path))
            for item in os.listdir(path):
                sub_path = os.path.join(path, item)
                self.del_dir(sub_path, min_ctime)
            if ctime < min_ctime and (not path in self.ignore_dirs):
                try:
                    os.rmdir(path)
                    logging.info(" path [{}] has been removed.".format(path))
                except OSError, err:
                    logging.warn(" path [{}] not removed because not empty".format(path))

    # clean up empty directories under a specific directory without deleting itself
    def clean_dir(self):
        min_ctime = datetime.datetime.now() - datetime.timedelta(seconds = self.get_seconds(self.max_age))
	for root_dir in self.root_dirs:
            if os.path.isdir(root_dir):
                for item in os.listdir(root_dir):
                    sub_path = os.path.join(root_dir, item)
                    self.del_dir(sub_path, min_ctime)
            else:
                raise Exception(" path [{}] does not exist.".format(root_dir))    
   
    def secheduled_action(self):
        self.clean_dir()

