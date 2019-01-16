import os, shutil, logging


class Mover():

    def __init__(self,
                 source = '/home/yadiw/Desktop/test.txt',
                 destination = '/home/yadi/Desktop/test2.txt'):
        self.source = source
        self.destination = destination

    def move(self):
        if not os.isdir(self.source):
            raise OSException( ' The given path for source directory does not exist.')
        if not os.isdir(self.destination):
            raise OSException( ' The given path for destination directory does not exist.')
        files = os.listdir(self.source)
        count = 0
        for f in files:
            count += 1
            src = os.path.join(self.source, f)
            dst = os.path.join(self.destination, f)
            shutil.move(src, dst)
        logger.info(' ')

if __name__ == '__main__':
    m = Mover()
    m.move()
