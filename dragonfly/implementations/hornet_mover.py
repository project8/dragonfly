from __future__ import absolute_import

import os, shutil, logging

from dripline.core import fancy_doc

logger = logging.getLogger(__name__)


@fancy_doc
class HornetMover(object):
    def __init__(self, src_dirs, dst_dir, **kwargs):
        '''
        A hornet mover moves one file at a time, while trying to keep the subdirectory structure the same as the one before moving.
        src_dirs: a list of possible source directories of a file before moving
        dst_dir : the destination directory of a file after moving.
        '''
        this_home = os.path.expanduser('~')
        self.src_dirs = []
        for directory in src_dirs:
            self.src_dirs.append(os.path.join(this_home, directory))
        self.dst_dir = os.path.join(this_home, dst_dir)
        if not os.path.exists(self.dst_dir):
            logger.warning(' The given destination does not exist.')
        
    def move_file(self, base_dir, sub_path):
        '''
        Move a file from its original path to the destination while keeping the original subdirectory structure, and return the new absolute path of the file.
        base_dir: the part of the original file path that will be replaced by the destination directory.
        sub_path: the part of the original file path that will be kept after the moving, including a series of subdirectories and the file name.
        '''
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
        '''
        A tiny method trying to split the given path in the right way, and return the two parts.
        path: an complete absolute path
        '''
        for base_dir in self.src_dirs:
            if path.startswith(base_dir):
                return base_dir, os.path.relpath(path, base_dir)
        return None, None

    # the one called by hornet
    def run(self, path):
        '''
        Move the given file and return its new path.
        path: the absolute path for the file to be moved.
        '''
        logger.debug(" I am trying to move " + path)
        base_dir, sub_path = self.get_sub_path(path)
        if sub_path:
            new_path = self.move_file(base_dir, sub_path)
            return new_path
        else:
            logger.error(' I cannot get the sub-path of ' + path)
            return path
