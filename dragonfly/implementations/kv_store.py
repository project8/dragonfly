""" kv_store.py

A simple key-value store which is a dripline provider.
The endpoints of this provider are associated with
keys, and are determined by the configuration file.
For example, if the configuration file has a provider
section that looks like this::

    providers:
      - name: kv_example
        module: kv_store
        endpoints:
          -name: foo
            module: kv_store_key
          -name: bar
            module: kv_store_key
          -name: baz
            module: kv_store_key


Then the KV store will have three keys, foo, bar, and
baz, which are associated with it.  They can be addressed
as such on the network, or can also be addressed using their
fully qualified hierarchical address e.g. somenode.kv.foo.
"""

from __future__ import absolute_import
import logging

from dripline.core import Provider, Spime, calibrate, fancy_doc

__all__ = ['kv_store', 'kv_store_key']


# Just a few dumb calibration functions for testing
def times2(value):
    return 2.*value
def times3(value):
    return 3.*value

logger = logging.getLogger(__name__)

@fancy_doc
class kv_store(Provider):
    """
    The KV store.  This is just a wrapper around a dict.
    """
    def __init__(self, **kwargs):
        Provider.__init__(self, **kwargs)

    def endpoint(self, endpoint):
        """
        Return the endpoint associated with some key.
        """
        return self.endpoints[endpoint]

    def list_endpoints(self):
        """
        List all endpoints associated with this KV store.
        This is the same as enumerating the keys in the
        dict.
        """
        return self.keys()

    def send(self, to_send):
        logger.info('asked to send:\n{}'.format(to_send))


@fancy_doc
class kv_store_key(Spime):
    """
    A key in the KV store.
    """
    def __init__(self, initial_value=None, **kwargs):
        Spime.__init__(self, **kwargs)
        self._value = initial_value
        self.get_value = self.on_get

    @calibrate([times2, times3])
    def on_get(self):
        """
        Return the value associated with this
        key.
        """
        value = self._value
        return str(value)

    def on_set(self, value):
        """
        Set the value associated with this key
        to some new value.
        """
        try:
            value = float(value)
            self._value = value - value % .01
        except ValueError:
            self._value = value
        return self._value
