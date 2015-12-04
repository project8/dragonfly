A Dragonfly powered key-value store
***********************************
As an exploration of the dripline protocol and how to use it with the dragonfly
package, let's create and work with a simple example. We will create a simple key-value
store, which simply records a set of values, which can be accessed by name.
This is certainly a bit contrived, but allows us to explore the interactions
common in a dripline-based system, without needing physical instrument. For this
reason, the kv_store is very commonly used in testing newly implemented features
when developing new features.

This tutorial is mostly meant as a quick exploration of the commandline tools
in dragonfly. There will be other tutorials covering specific tasks in more detail including writing new config files or creating new endpoints and providers.

.. todo:: create a writing config files tutorial and link it
.. todo:: create a developing extension classes tutorial and link it

Getting Started
---------------
Each package, dripline and dragonfly, includes a ``README.md`` file which has
simple instructions for installation. You can find more detailed instructions in the 
:doc:`/getting_started` section. In each case, there are basically three steps:

1. **Prepare your environment:** Usually this amounts to activating a virtualenvironment, or creating one if needed. Further discussion of why you would do this is beyond the scope of this tutorial, but rest assured that it is a very very good idea.
2. **Install dependencies:** The easiest way to do this is to simply run ``pip install -r requirements.txt`` (or possible a more specific requirements file, also provided).  In most cases setuptools is also capable of installing dependencies, or you are welcome to install them yourself by hand using pip, easy_install, or whatever other method you like.
3. **Install the package:** Again, this is easily done with ``python setup.py [install|develop]``, where you use "install" if you just want things to work, or "develop" if you plan to be making changes to the code and want to test them without re-installing each time.



Deprecated
**********
The following sections are all from the old tutorial. They will be removed as this tutorial becomes more fully flushed out.



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

We can write a configuration file for dripline (note, this exact file is in ``
examples/kv_store_tutorial.yaml``) that looks like this and represents our
pricelist in a very recognizable way:

.. code-block:: yaml

  nodename: my_store
  broker: localhost
  providers:
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

That's it.  The ``nodename`` parameter is simply telling dripline that we want
our dripline node to be called ``my_store``.  The ``broker`` is telling 
dripline that there is an AMQP router which is installed on localhost.  
In the ``providers`` section, we declare a provider named ``my_price_list``, 
with the ``module`` parameter set to ``kv_store``.  When dripline sees the 
``module`` parameter, it will look to see what that string value corresponds to
in terms of the object that it should construct.  In this case, it will 
construct an object of type ``KVStore`` and give it the name ``my_price_list``.
The ``endpoints`` of ``my_price_list`` correspond to the prices of each
individual item.  Each endpoint has a ``name``, which is simply the name of the
item, and a ``module``, which is identical to the idea of a provider module.

The only new thing here is the ``initial_value`` parameter, which you notice
is equal in each case to the initial price of the object of the same name
as the endpoint.  Dripline considers every parameter which isn't called 
``name`` or ``module`` to be *specific to the object* and passes it along to
the object for it to do with as it likes.  In this instance, the initializer
of the ``KVStoreKey`` object looks like this:

.. code-block:: python

 def __init__(self, name, initial_value=None):
        self.name = name
        self.provider = None
        self.initial_value = initial_value

Note that initial_value is a keyword argument to the constructor, which sets
whatever that parameter may be to be the initial value associated with the
key.  

Interacting with it
-------------------
OK, enough details.  To fire up our key-value store and start interacting with
it, we want to start a dripline node which will use our configuration file.
To do that, we will use :ref:`open_spimescape_portal` located in the bin directory.
We point it to our configuration file (if you are intrepid enough to make your
own, point to whatever you created), and fire it up:

.. code-block:: bash

  $ open_spimescape_portal -c examples/kv_store_tutorial.yaml -vvv

Notice the ``-vvv`` which sets the output to its most verbose. For each "v" you
omit, one logging severity level will be omited. If no ``-v`` option is given,
normal operation should produce no terminal output. If you do the above, you should
see output that looks like this:

.. literalinclude:: kv_store_service_startup_output.log
    :language: bash

This isn't too hard to follow - dripline starts up, connects to the broker
you told it to, adds a provider and the endpoints, and is ready to go.

Now let's start getting some prices.  We're going to use ``dripline_agent``
to do this, as it gives us a very easy way to interact with dripline 
endpoints from the command line.  First of all, let's check the current
price of peaches:

.. code-block:: bash

    $ dripline_agent -b localhost get peaches
    2014-09-08 13:45:57,905 - node - INFO - connecting to broker localhost
    peaches: 0.75

Nice.  So the current price of peaches in our store is 0.75.  What about
waffles?

.. code-block:: bash

    $ dripline_agent -b localhost get waffles
    2014-09-08 13:52:26,597 - node - INFO - connecting to broker localhost
    waffles: 4.0

If you have another computer on your local network (or any network that can see
your amqp broker) then you can do the same thing from there:

.. code-block:: bash
   
    (on_amqp_server) $ dripline_agent -vvv get waffles
    2015-01-15T13:00:30Z[INFO    ] dripline.core.node(22) -> connecting to broker None
    waffles: 4.0
    
    (on_some_other_server) $ dripline_agent -b <amqp.broker.server.address> get peaches
    peaches: 0.75

Note again that the ``-v`` option can be given to increase the output verbosity.

Now let's say that there's been a global rush on chips and the price we
have to charge has skyrocketed from 1.75 to 1.79.  We can use 
``dripline_agent`` to set the new value:

.. code-block:: bash

  $ dripline_agent -b localhost get chips
  2014-09-08 13:53:57,432 - node - INFO - connecting to broker localhost
  chips: 1.75
  
  $ dripline_agent -b localhost set chips 1.79
  2014-09-08 13:53:38,545 - node - INFO - connecting to broker localhost
  chips->1.79: complete
  
  $ dripline_agent -b localhost get chips
  2014-09-08 13:53:59,768 - node - INFO - connecting to broker localhost
  chips: 1.79
