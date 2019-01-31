import os, shutil, logging, Queue, ast

logger = logging.getLogger(__name__)

class HornetMover():
    def __init__(self, src_dirs, dst_dir, **kwargs):
        self.src_dirs = src_dirs
        self.dst_dir = dst_dir
        if not os.path.exists(self.dst_dir):
            logger.warning(' The given destination does not exist.')
        
    # moving one file 
    def move_file(self, base_dir, sub_path):
        src = os.path.join(base_dir, sub_path)
        if not os.path.exists(src):
            logger.warning(' The given path for source file is invalid.')
            return src
        dst = os.path.join(self.dst_dir, sub_path)
        if not os.path.exists(os.path.dirname(dst)):
            try:
                os.makedirs(os.path.dirname(dst))
            except OSError:
                logger.error(' Unable to create directories in ' + self.dst_dir)
                os._exit(1)
        shutil.move(src, dst)
        logger.debug(' Moved ' + sub_path + ' from ' + src + ' to ' + dst)
        return dst
    
    def get_sub_path(self, path):
        for base_dir in self.src_dirs:
            if path.startswith(base_dir):
                return base_dir, os.path.relpath(path, base_dir)
        return None, None


    def run(self, path):
        logger.debug(" I am trying to move " + path)
        base_dir, sub_path = self.get_sub_path(path)
        if sub_path:
            new_path = self.move_file(base_dir, sub_path)
            return new_path
        else:
            logger.error(' I cannot get the sub-path of ' + path)
            return path
