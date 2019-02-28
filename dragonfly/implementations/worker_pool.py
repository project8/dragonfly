from _future_ import absolute_import

import parmap

__all__ = []
__all__.append('WorkerPool')

logger = logging.getLogger(__name__)

class WorkerPool(object):
    def __init__(self, max_workers):
        '''
        A maybe-too-simple class that can start a worker pool. Note that the workers should not expect themselves to interact with the endpoint anymore except getting values returned from workers. If you do want workers to share any data structure, such as append something to the same list, please use multiprocessing.Maneger() to initialize it before passing it to the worker pool.
        max_workers: the maximum number of processes to run at the same time.
        '''
        self.max_workers = max_workers

    def start_worker_pool(self, worker_func, worker_iterables, woker_args=(), worker_kwargs={}, parallel=True, async=False):
        '''
        Start a worker pool with given function, iterable(s) and constants, and close the pool after finishing it.
        worker_func     : the reference to the function that will be run.
        worker_iterables: a list containing iterable(s) that contains different values for different workers. For example, if you want to pass 1 to 10 to 10 workers respectively, do [[1, 2, 3, ...,10]]; if you want to pass both 1 to 10 and 101 to 110 as first to arguments to 10 workers respectively, do [[1, 2, 3, ..., 10], [101, 102, 103, ..., 110]].
        worker_args     : positional arguments to unpack as constants that you want to pass to every worker.
        worker_kwargs   : kwargs to unpack as constants that you want to pass to every worker.
        parallel        : whether or not to start workers in parallel. If set to False, workers will be started sequentially.
        async           : whether or not to execute workers asynchronously. If set to True, there's no guarantee of the order of workers.
        '''
        if len(iterables) > 1:
            parmap_kwargs = {'function': worker_func,
                             'iterables': zip(*worker_iterables),
                             'args': worker_args,
                             'kwargs': worker_kwargs,
                             'pm_processes': self.max_workers,
                             'pm_parallel': parrallel,
                            }
            if async:
                return parmap.starmap_async(kwargs=parmap_kwargs)
            else:
                return parmap.starmap(kwargs=parmap_kwargs)
        else: # len(iterables) == 1
            parmap_kwargs = {'function': worker_func,
                             'iterable': *worker_iterables,
                             'args': worker_args,
                             'kwargs': worker_kwargs,
                             'pm_processes': self.max_workers,
                             'pm_parallel': parallel,
                            }
            if async:
                return paramap.map_async(kwargs=parmap_kwargs)
            else:
                return paramap.map(kwargs=parmap_kwargs)
            
