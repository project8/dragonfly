import random
import sys

from dripline.core.calibrate import calibrate
from dripline.implementations import KeyValueStore
__all__ = []

__all__.append("JitterEntity")
class JitterEntity(KeyValueStore):
    '''
    A simple endpoint which stores a value but returns that value + a random offset
    '''

    def __init__(self, jitter_fraction=0.1, seed=None, **kwargs):
        '''
        Args:
            jitter_fraction (number): scaling factor for the random jitter factor
            seed (int||None): value to use to seed the PRNG
        '''
        KeyValueStore.__init__(self, **kwargs)
        self._jitter_fraction = jitter_fraction
        self.update_seed(seed)

    @calibrate()
    def on_get(self):
        return self._value * (1 + self._jitter_fraction * random.random())

    @property
    def seed(self):
        return self._seed
    @seed.setter
    def seed(self, new_seed=None):
        ## There is no reason why update_seed needs to be a separate function, except
        ## that I also want to demo interacting with an arbitrary normal method
        self.update_seed(new_seed)

    def update_seed(self, new_seed=None):
        '''
        Updates the PRNG seed to the provided new_seed, or generates one if it is None.

        *Note* you generally don't need to do this, it is just here to serve as an example
        of adding and using a function with arbitrary logic.
        '''
        if new_seed is None:
            self._seed = random.randrange(sys.maxsize)
        random.seed(self._seed)
