from __future__ import absolute_import

import logging
import multiprocessing
import time, os

import itertools

__all__ = []
__all__.append('WorkerPool')

logger = logging.getLogger(__name__)

import copy_reg, types

class WorkerPool(object):
    def __init__(self, max_workers):
        self.max_workers = max_workers
        self.pool = multiprocessing.Pool(processes=self.max_workers)

        def _pickle_method(m):
            if m.im_self is None:
                return getattr, (m.im_class, m.im_func.func_name)
            else:
                return getattr, (m.im_self, m.im_func.func_name)
        copy_reg.pickle(types.MethodType, _pickle_method)

    #def __getstate__(self): # unnecessary in container - but let's keep it
    #    self_dict = self.__dict__.copy()
    #    del self_dict['pool']
    #    return self_dict

    def worker(self, pair):
        func, args = pair
        return func(*args)

    def unpack_pack(self, func, iterables, constants):
        iterable_len = len(iterables[0])
        for iterable in iterables:
            this_len = len(iterable)
            if this_len != iterable_len:
                logger.warning(' All iterables are supposed to have same length... I will follow the shortest one.')
                break
        result_list = [list(elem) for elem in (zip(*iterables))]
        result_tuple = []
        for i in result_list:
            i.extend(list(constants))
            result_tuple.append((func, i))
        return result_tuple

    def start_worker_pool(self, func, iterables=[], constants=[]):
        logger.debug(' Trying to start a worker pool with ' +  str(iterables) + '    '+ str(constants))
        if not (isinstance(iterables, list) and isinstance(constants, list)):

            logger.error(" Don't forget to put iterables and constants in lists")
            return
        if len(iterables) == 0:
            logger.warning(" I receive no iterables... Will do this sequentially.")
            return func(*constants)
        if len(constants) == 0:
            logger.debug(' I get only iterables!')
            iterable = zip(*iterables)
            r = self.pool.map(self.worker, iterable)
        else:
            logger.debug(' I get both iterables and constants!')
            args_tuple = self.unpack_pack(func, iterables, constants)
        r =  self.pool.map(self.worker, args_tuple)
        return r
        
class Class(WorkerPool): # for testing
    def __init__(self):
        WorkerPool.__init__(self, 5)

    def something(self, num, num2, sentence, l1, a_list):
        for i in range(num):
            time.sleep(1)
            print(i)
        print('--------done-----------' + str(num))
        print(sentence + str(num2))
        print(l1)
        a_list.append(num + num)
        return num * num

    def a_splendid_method(self, sth):
        print(str(sth) + ' this is a great method!!!')

    def somethingelse(self):
        start_time = time.time()
        a_list = multiprocessing.Manager().list()
        r = self.start_worker_pool(self.something, [range(10), range(15)], ['I am cool!', 'something', a_list])
        print("--- %s seconds ---" % (time.time() - start_time))
        print(a_list)
        return r

if __name__ == '__main__':
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    c = Class()
    result = c.somethingelse()
   
    
