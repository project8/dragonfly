============
Introduction
============

Dragonfly is a dripline-based slow-control implementation in python.

Dripline Basics
===============

More complete introductions to `dripline <https://dripline.readthedocs.io/en/latest/>`_ or the `python-implementation <https://dripline-python.readthedocs.io/en/latest/>`_ are available in their specific documentation.

Dripline defines the wire protocol standard, i.e. how the messages are packaged and what fields to expect.
In practice, we run primarily Linux machines on Debian Stretch (9.x) with the system package version of RabbitMQ (3.6.6) to serve as our routing system.
By design, however, dripline is agnostic to those choices so that we can fluidly interface between Windows machines with Labview applications, Mac laptops where users are testing, and Linux machines running C++-based DAQ software or python-based slow-control.

Dripline-python is the python-specific implementation of the dripline standard.
It handles all the dripline compliance that you don't want to worry about - adherence to the wire protocol, connections to the RabbitMQ broker, packing and unpacking of messages, etc.
It also provides a suite of functionality that dragonfly implementations will want to take advantage of - a custom set of error codes and exceptions with additional information, a mechanism for scheduling regularly-occurring actions, direct communication with any other service on the dripline mesh.
