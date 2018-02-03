A Dragonfly powered key-value store
**********************************
As a way to explore how dragonfly creates sensors that we can interact with
via the dripline protocol, let's create and interact with a simple example:
a key-value store which is implemented as a dripline endpoint.  The key-value
store will be very simple: a list of keys, each of which is a string (for
example, ``key0``, ``foo_key``, ``some_name``, whatever).  Associated with
each key is a floating point number which is its value: 1.3 perhaps, or -3.4,
or 1.4e21, or really anything that can represent a floating point number.
What we want as a user is some remote storage for such a key-value store, where
we can ask dripline for the current value of ``key0`` and have it answer with
whatever that current value may be.


A quick refresher
-----------------
First let's recall how things are structured in dripline-python.
The most basic functional unit in a dripline node is an *endpoint*.
An endpoint represents something that we want to interact with - perhaps it is
the contents of some file in a directory, or the input to a voltmeter, or
in this case, a value associated with some key.  In a dripline configuration
file, an endpoint is always declared in a block whose name is ``endpoints``.

**Every** endpoint must have a *provider* associated with it.  The concept
of a provider represents an element in the system without which an endpoint
could not independently function.  For example, consider a case where an
endpoint represents the input to a digital voltmeter which is connected to
an ethernet router.  Without a connection to the voltmeter, we clearly can't
communicate with the endpoint.  For that reason, we may write some code which
performs the communication with the voltmeter itself, and then we say that
code *provides* the endpoint which is the input to the voltmeter.  It's also
the case that once we have one connection to the voltmeter, it seems like
wasted effort to duplicate that among many objects, and so the voltmeter
provider can act as a logical way to group endpoints together.

Let's go
--------
To start with, let's consider the structure of our key-value store.  We
have a list of some keys that have string names, and each key has a floating
point value associated with it.  We will consider a list of items at a store,
each of which has a price in dollars.  It's not a very big store - we only
have peaches, chips, and waffles.  The prices of these items fluctuates a lot
due to global waffle demand, and so we want to be able to both ask our system
what the current price is, and change the prices as necessary.

The dripline ``kv_store`` provider and ``kv_store_key`` endpoint will give us
exactly this in a very simple way.  If the current pricelist is something like

* Peaches: 0.75
* Chips: 1.75
* Waffles: 4.00

We can write a configuration file for dragonfly (note, this is a reduced version
of ``examples/kv_store_tutorial.yaml``) that looks like this and represents our
pricelist in a very recognizable way:

.. code-block:: yaml

  name: my_store
  broker: localhost
  module: Spimescape
  endpoints:
    - name: my_price_list
      module: kv_store
      endpoints:
        - name: peaches
          module: kv_store_key
          initial_value: 0.75
        - name: chips
          module: kv_store_key
          initial_value: 1.75
        - name: waffles
          module: kv_store_key
          initial_value: 4.00


That's it.
Note in this modular structure that each level will have a ``name`` and ``module``, and if it is a "Provider" it may have ``endpoints`` under it.
Each ``name`` will correspond to a binding to the AMQP queue created.
Throughout the config, the string value in the ``module`` field is referenced against the imported classes to find which object should be constructed.
If the module takes arguments as enumerated in its initializer (``__init__``), those will be included at the same level (``broker`` for ``Spimescape`` and ``initial_value`` for ``kv_store_key``).

At the top level, the ``name`` parameter is simply telling dripline that we want our dripline node to be called ``my_store``.
The ``broker`` is telling dripline that there is an AMQP router which is installed on localhost.
The ``module`` is telling dragonfly to create an instance of Spimescape, which is the most basic class for interacting with the dripline mesh.
In the ``endpoints`` section, we declare the "endpoints" under ``my_store``.

In the second level, we enumerate those endpoints, here only a single one with ``name`` of ``my_price_list``.
The ``module`` is ``kv_store``, which instructs dragonfly to construct an object of type ``KVStore``.
The top-level ``Spimescape`` module is for generic interaction with the dripline mesh, whereas this ``KVStore`` contains any specific implementation.
Again, as a provider, it has an ``endpoints`` section to declare the next level which will be the key-value pairs of interest.

At the bottom level, the ``name`` is the name of the item (the key) and the ``initial_value`` is the starting price (the value).
The ``module`` again instructs dragonfly to construct objects of type ``KVStoreKey``.
It is instructive to note that there is no special relationship between the provider ``KVStore`` and endpoint ``KVStoreKey``, one could add other endpoints from a different module.

Here we have an additional argument for each endpoint in ``initial_value``.
Dripline considers every parameter which isn't called ``name`` or ``module`` to be *specific to the object* and passes it along to the object for it to do with as it likes.
In this instance, the initializer of the ``KVStoreKey`` object looks like this:

.. code-block:: python

  def __init__(self, initial_value=None, **kwargs):
      self._value = initial_value

Note that initial_value is a keyword argument to the constructor, which sets whatever that parameter may be to be the initial value associated with the key.

Interacting with it
-------------------
OK, enough details.
To fire up our key-value store and start interacting with it, we want to start a dripline node which will use our configuration file.
To do that, we will use :ref:`dragonfly` located in the bin directory with argument ``serve`` which invokes the :ref:`open_spimescape_portal` in the dragonfly/subcommands directory.
We point it to our configuration file (if you are intrepid enough to make your own, point to whatever you created), and fire it up:

.. code-block:: bash

  $ dragonfly serve -c examples/kv_store_tutorial.yaml -vvv

Notice the ``-vvv`` which sets the output to its most verbose.
For each "v" you omit, one logging severity level will be omitted.
If no ``-v`` option is given, normal operation (no warnings) should produce no terminal output.
If you do the above, you should see output that looks like this:

.. literalinclude:: kv_store_service_startup_output.log
    :language: bash

There is high verbosity in the output, but not too much to follow.
First dragonfly starts up and you can see that it will call open_spimescape_portal and the complete dictionary loaded from the config file.
Then open_spimescape_portal creates in order each of the modules specified.
At the first line break (-----) all modules have been constructed, the rest is AMQP magic.

First the connection to the AMQP broker is established.
Then the relevant exchanges and queue are declared.
Then all the bindings are established; everything in the config file with a ``name`` plus the global "broadcast" gets its own binding to the queue.

Now let's start getting some prices.
We're going to use ``dragonfly`` to do this again, but with the the argument ``get``, which invokes the :ref:`dripline_agent` in the dragonfly/subcommands directory.
This is the common starting point for all interaction with dripline endpoints.
First of all, let's check the current price of peaches:

.. code-block:: bash

    $ dragonfly get peaches
    warning: slack is only ever warning, setting that
    peaches(ret:0): [my_store]-> {u'value_raw': u'0.75'}

Nice.
So the current price of peaches in our store is 0.75.
We can also see that peaches is bound to the ``[my_store]`` queue (in case you forgot), and that it had a successful return code ``(ret:0)``.
If you missed all that verbosity, you could again turn it on with a ``-vvv`` option, but that is mostly distracting.

What about waffles?

.. code-block:: bash

    $ dragonfly get waffles
    warning: slack is only ever warning, setting that
    waffles(ret:0): [my_store]-> {u'value_raw': u'4.0'}

By default, dragonfly tries to connect to the broker on localhost.
Dragonfly allows the broker to be specified with ``-b`` flag, so the above commands were identical to using a ``-b localhost`` option.
If you have another computer on your local network (or any network that can see your amqp broker) then you can still query the endpoints by providing the broker address:

.. code-block:: bash

    (on_amqp_server) $ dragonfly get peaches
    warning: slack is only ever warning, setting that
    peaches(ret:0): [my_store]-> {u'value_raw': u'0.75'}

    (on_amqp_server) $ dragonfly get peaches -b localhost
    warning: slack is only ever warning, setting that
    peaches(ret:0): [my_store]-> {u'value_raw': u'0.75'}

    (on_some_other_server) $ dragonfly get peaches -b <amqp.broker.server.address>
    warning: slack is only ever warning, setting that
    peaches(ret:0): [my_store]-> {u'value_raw': u'0.75'}

Now let's say that there's been a global rush on chips and the price we have to charge has skyrocketed from 1.75 to 1.79.
We can use ``dragonfly`` again to set the new price, using the ``set`` argument.
Again this invokes :ref:`dripline_agent`:

.. code-block:: bash

    $ dragonfly get chips
    warning: slack is only ever warning, setting that
    chips(ret:0): [my_store]-> {u'value_raw': u'1.75'}

    $ dragonfly set chips 1.79
    warning: slack is only ever warning, setting that
    chips->1.79(ret:0): [my_store]-> {u'values': [1.78]}

    $ dragonfly get chips
    warning: slack is only ever warning, setting that
    chips(ret:0): [my_store]-> {u'value_raw': u'1.78'}

How did chips only get set to 1.78 when I explicitly asked for 1.79?
A reasonable question, but one which quickly devolves into a discussion of floating point arithmetic in python 2.
If you look in kv_store.py, you will discover that the ``on_set`` method attempts ``self._value = value - value % .01``, i.e. it is rounding to the nearest cent.
But the modulus in fractional division doesn't make sense with floats, just open a python terminal:

.. code-block:: python

    >>> value = 1.79
    >>> value - value % .01
    1.78

And on that disappointing note, we close.
