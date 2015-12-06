***********************************
A Dragonfly powered key-value store
***********************************
As an exploration of the dripline protocol and how to use it with the dragonfly
package, let's create and work with a simple example. We will create a simple key-value
store, which simply records a set of values, which can be accessed by name.
This is certainly a bit contrived, but it allows us to explore the interactions
common in a dripline-based system without needing a physical instrument. For this
reason, the kv_store is very commonly used in testing newly implemented features.

This tutorial is mostly meant as a quick exploration of the commandline tools
in dragonfly. There will be other tutorials covering specific tasks in more detail including writing new config files or creating new endpoints and providers.

.. todo:: create a developing extension classes tutorial and link it

Getting Started (from scratch)
------------------------------
There are two steps here, installing/starting an AMQP server is required if you are
doing local development, independent of a running system. It is certainly possible
to work with an existing server, but for development you are encouraged to work
locally, both to ease debugging and to avoid breaking "production" components.

AMQP Broker (RabbitMQ)
======================
For detailed instructions, you should visit `the official website <https://www.rabbitmq.com/download.html>`_
and check the section for your operating system. In the case of debian it is a simple as:

.. code-block:: sh

    sudo apt-get install rabbitmq server
    sudo rabbitmq-server start

Dragonfly works with a vanilla installation of rabbitmq, though there exists support
for user authentication. Users are required if deploying a system across multiple
computers (ie in any realistic production system). For this example we're going to just
work locally and save that for later.

Dragonfly Installation
======================

Each package, dripline and dragonfly, includes a ``README.md`` file which has
simple instructions for installation. You can find more detailed instructions in the 
:doc:`/getting_started` section. In each case, there are basically three steps:

1. **Prepare your environment:** Usually this amounts to activating a virtualenvironment, or creating one if needed. Further discussion of why you would do this is beyond the scope of this tutorial, but rest assured that it is a very very good idea.
2. **Install dependencies:** The easiest way to do this is to simply run ``pip install -r requirements.txt`` (or possible a more specific requirements file, also provided).  In most cases setuptools is also capable of installing dependencies, or you are welcome to install them yourself by hand using pip, easy_install, or whatever other method you like.
3. **Install the package:** Again, this is easily done with ``python setup.py [install|develop]``, where you use "install" if you just want things to work, or "develop" if you plan to be making changes to the code and want to test them without re-installing each time.

What's in a config file?
------------------------
The configuration file for our key-value store is named ``kv_store_tutorial.yaml`` and can
be found in the ``examples/`` directory. In this section we'll review the contents of 
that file and how one might go about writing one from scratch. Feel free to skip this
section and come back later if you are currently working with a running system and not
interested in new config files yet.

Just to get started, let's look at the full configuration file for the key-value store.

.. literalinclude:: ../../examples/kv_store_tutorial.yaml
    :language: yaml
    :linenos:
    :emphasize-lines: 1-4,8-14,22-27

The stripped highlighting divides the above config file into blocks, each of which
will be used to create a python object when the service is started. Within each
block there are (currently) four reserved keys [name, module, module_path, endpoints].

* **name:** is always required and must be a string; it specifies the binding key for whic the object will listen to messages (and should be unique across all services)
* **module:** is the python class of which the object will be an instance. In the case of the first/top level object, this field is optional and defaults to "Spimescape" if missing (this is done for backward compatibility, preferred usage is to always specify).
* **module_path:** allows the user to provide a class implementation which is not part of dragonfly. The path must be to a python source file which implements the "module" named. This is intended to make it easier to test new object implementations, and to allow use of objects which are so case-specific that they don't really belong in dragonfly.
* **endpoints:** should only be present if the "module" is a subclass of ``Provider``. If present, it contains a list of object configurations for objects which should use this instance as their provider.

All other elements describe parameters of the instance and are passed to
``<module>.__init__()`` when the service is creating the instances. Note that
dripline and dragonfly make heavy use of multi-generational inheritance. Each
child class can implement new kwargs to ``__init__``, but pass all others to
the parent class. Therefore, the config file may contain kwargs for the class
or any of its ancestors. If you want to know what parameters are available,
the easiest (and most likely up-to-date) way is to use the [i]python interpretor
to print the class's doc string (note that dragonfly uses introspection to
update the doc string at runtime, so this is generally more complete than the
docstring present in the source). If, for example, you wanted to see what is
available for a ``kv_store_key`` instance, you would use the following two lines

.. code-block:: python

    >>> import dragonfly
    >>> help(dragonfly.implementations.kv_store_key)

Which would open your shell's pager with output that starts like the following:

.. code-block:: sh

    Help on class kv_store_key in module abc:
    
    class kv_store_key(dragonfly.implementations.kv_store.kv_store_key)
    |  A key in the KV store.
    |  
    |  Keyword Args:
    |      log_on_set (bool): flag to enable logging the new value whenever a new one is set
    |      name (str): unique identifier across all dripline services (used to determine routing key)
    |      calibration (str||dict): string use to process raw get result (with .format(raw)) or a dict to use for the same purpose where raw must be a key
    |      get_on_set (bool): flag to toggle running 'on_get' after each 'on_set'
    |      log_interval (float): minimum time in seconds between sequential log events (note that this may or may not produce an actual log broadcast)
    |      max_interval (float): If > 0, any log event exceding this number of seconds since the last broadcast will trigger a broadcast.
    |      max_fractional_change (float): If > 0, any log event which produces a value which differs from the previous value by more than this amount (expressed as a fraction, ie 10% change is 0.1) will trigger a broadcast
    |      alert_routing_key (str): routing key for the alert message send when broadcasting a logging event result. The default value of 'sensor_value' is valid for DataLoggers which represent physical quantities being stored to the slow controls database tables
    |  


Running it all
--------------

To run and interact with our service, we will make use of various subcommands of
the ``dragonfly`` program. It has a fairly complete commandline help for both
the base command and the various subcommands, all accessible using the ``-h`` flag.

So to get a listing of the available subcommands, we will run ``dragonfly -h`` and see:

.. code-block:: sh

    usage: dragonfly [-h] {get,set,config,run,cmd,send,monitor,serve,watchdog} ...

    optional arguments:
    -h, --help            show this help message and exit

    subcommands:
    detailed help is available for each subcommand

    {get,set,config,run,cmd,send,monitor,serve,watchdog}
    get                 return the value of an endpoint or a property of an
                        endpoint if specified
    set                 set the value of an endpoint, or a property of an
                        endpoint if specified
    config              <deprecated> query or set the value of a property of
                        an endpoint
    run                 send an OP_RUN, further details are endpoint specific
    cmd                 have an endpoint execute an internal function
    send                have an endpoint (which is probably also a provider)
                        execute a send
    monitor             utility for listening in on AMQP messages (does not
                        prevent delivery but may prevent undeliverable errors
                        if there is no other valid target)
    serve               start a long-running dripline service based on a
                        provided config file (formerly open_spimescape_portal)
    watchdog            utility for making sure some data is always showing up


Running the monitor
===================

To start, we will use the monitor. It binds to the AMQP exchange with a configurable
binding key, and prints all messages received. This is especially useful when debugging
to see if messages are being sent or to check intermediate steps. We can
review the usage and options with ``dragonfly monitor -h``:

.. code-block:: sh

    usage: dragonfly monitor [-h] [-v] [-V] [-b [BROKER]] [-c CONFIG] [-t [TMUX]]
                             [--no-slack] [-e exchange name]
                             [-k [keys [keys ...]]] [-po]
    
    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         increases terminal output verbosity
      -V, --version         display dripline version
      -b [BROKER], --broker [BROKER]
                            network path for the AMQP broker, if not provided (and
                            if a config file is provided) use the value from the
                            config file; if the option is present with no argument
                            then "localhost" is used
      -c CONFIG, --config CONFIG
                            path (absolute or relative) to configuration file
      -t [TMUX], --tmux [TMUX]
                            enable running in, and optionally naming, a tmux
                            session
      --no-slack            disable the status log handler to post critical
                            messages to slack
      -e exchange name, --exchange exchange name
                            amqp name of the exchange to monitor
      -k [keys [keys ...]], --keys [keys [keys ...]]
                            amqp binding keys to follow
      -po, --payload-only   Print only the message.payload

The ``-po`` flag is interesting, is displays a much less verbose version of all messages,
so we will use that for now, along with ``-e`` to specify the "requests" exchange. By
default the "alerts" exchange is used. We do not need to specify a key with ``-k``
because the default is the all keys wildcard.

Open up either a new terminal or tmux pane (and activate your virtual environment in it)
and then run ``dragonfly monitor -e requests -v``. This is a forground process so we 
will see a few initial messages as it starts up, then it will sit blocking the terminal
while waiting for new messages to be printed (the ``-v`` may be omitted, but the
less will be printed and it can sometimes be hard to tell if it is running).


Starting the Key-Value service
==============================

Next, we will start our key-value store service, first reminding ourselves of the
command usage:

.. code-block:: sh

    usage: dragonfly serve [-h] [-v] [-V] [-b [BROKER]] [-c CONFIG] [-t [TMUX]]
                           [--no-slack] [-k BINDING_KEYS]
    
    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         increases terminal output verbosity
      -V, --version         display dripline version
      -b [BROKER], --broker [BROKER]
                            network path for the AMQP broker, if not provided (and
                            if a config file is provided) use the value from the
                            config file; if the option is present with no argument
                            then "localhost" is used
      -c CONFIG, --config CONFIG
                            path (absolute or relative) to configuration file
      -t [TMUX], --tmux [TMUX]
                            enable running in, and optionally naming, a tmux
                            session
      --no-slack            disable the status log handler to post critical
                            messages to slack
      -k BINDING_KEYS, --keys BINDING_KEYS
                            amqp binding keys to match against

So moving to another terminal or tmux pane (again with our virtual environment active),
we start the service with ``dragonfly serve -c examples/kv_store_tutorial.yaml -v``.
Again, we will see some messages as it starts up, and can omit ``-v`` to silence output
or add ``-vv`` to have extremely verbose output of what our service is doing.


Queries to the service
======================

Great, so now we have a running dripline service, started with dragonfly. What if
we want to see the current value of the "peaches" endpoint? We use the "get" subcommand.
You should know how to check the syntax by now, the answer is ``dragonfly get peaches``
and should return something that looks like the following:

.. code-block:: sh

    peaches(ret:0): {u'value_cal': 1.5, u'value_raw': u'0.75'}

So we see the raw and calibrated values. The monitor should display something like the following
two messages. The first is our "get" request, and the second is the reply sent back to it.
In the case of the key-value store, the expectation is two similar messages for any request
we may send. In more complicated instrument interactions there could be several because
one endpoint may need to make its own requests to other endpoints in order to properly respond.

.. code-block:: sh

    2015-12-04T17:25:03[Level 35] dragonfly.subcommands.message_monitor(34) -> 
    dripline.core.Service [peaches]     (From App [routing_key])
    {
        "timestamp": "2015-12-05T01:25:03Z", 
        "sender_info": {
            "username": "laroque", 
            "exe": "/home/laroque/python_environments/more_alerts/bin/dragonfly", 
            "package": "dripline", 
            "hostname": "higgsino", 
            "version": "wp1.4.0", 
            "commit": "g5c3ea72"
        }, 
        "payload": {
            "values": []
        }, 
        "msgop": 1
    }
    2015-12-04T17:25:03[Level 35] dragonfly.subcommands.message_monitor(34) -> 
    dripline.core.Service [request_reply582034c6-ebbf-4379-9dc9-6a0b159b7527]     (From App [routing_key])
    {
        "timestamp": "2015-12-05T01:25:03Z", 
        "sender_info": {
            "username": "laroque", 
            "exe": "/home/laroque/python_environments/more_alerts/bin/dragonfly", 
            "package": "dripline", 
            "hostname": "higgsino", 
            "version": "wp1.4.0", 
            "commit": "g5c3ea72"
        }, 
        "retcode": 0, 
        "return_msg": "", 
        "payload": {
            "value_cal": 1.5, 
            "value_raw": "0.75"
        }
    }

Seeing logger broadcasts
========================

Now that we have seen the basic request/reply messages in the monitor, we can turn it off,
and instead run it bound to the alerts exchange. This is where services broadcast individual
messages which are not part of a request/reply pair. The syntax is similar, but the default
"alerts" exchange is what we want, and the ``-po`` option is probably desirable
(``dragonfly monitor --po``). This will allow us to see any values that our endpoints may broadcast.

For a start, we can change the value of peaches, maybe ``dragonfly set peaches 0.64``
for a new value. Notice that in the monitor we see the following:

.. code-block:: json

    2015-12-06T09:18:08[Level 35] dragonfly.subcommands.message_monitor(34) ->
    dripline.core.Service [sensor_value.peaches]     (From App [routing_key])
    {
      "value_cal": 1.24,
      "value_raw": "0.62"
    }

If we look back to line 14 of the config file, we see that peaches are configured with "log_on_set"
set to True. This is interesting; it means that whenever the value of peaches gets changed
the endpoint will broadcast the new value (useful, for example, if another service is listening
for those broadcasts and storing the endpoint values into a database).


Timed logger broadcasts
=======================

If our peaches endpoint were not just a store, but represented a measurement (such as a temperature
sensor for example), then we would not have a "set" to trigger logs when there are new values.
To deal with this, we can have the log on a timed schedule. By default, when you start a service
the timed loggers are not started. This is done because one often needs to confirm or alter
some configurations before the loggers should actually start broadcasting.

We can use the "set" subcommand to configure a property of an endpoint, in addition to the 
vaule of the endpoint itself. That syntax is ``dragonfly set peaches.logging_status on``
(note the '.' delimiter which allows us to specify a property name, and that we provide a value.

You should now see a new value broadcast printed in the message monitor every 30 seconds.
Those should all look the same, since the peaches value is just whatever value is stored,
but you can use ``dragonfly set peaches 0.45`` (or any other value) and see that the value
being broadcast changes.

As a convenience, because a single provider often has many endpoints which are loggers,
all of the endpoints associated with a provider may have their "logging_status" configured at
once, by sending the "set" command to the provider instead (``dragonfly set my_price_list.logging_status on``).

