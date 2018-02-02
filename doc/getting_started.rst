===============
Getting Started
===============

Actually installing dragonfly is quite easy, but has various dependencies discussed in the following section.
The recommended installation procedure follows that discussion.

System Requirements
*******************
The development of dragonfly is being done primarily on OS X (with packages installed via homebrew and python packages through pip) and debian linux (with packages obviously from pip and python packages through pip).
No strange dependency on Debian version (Jessie and Stretch tested as of early 2018) or OS X release has been found.

We have made no attempt to determine the minimal system requirements, but develop primarily in python 2.7 with "current" versions from PyPI.
No effort is made to maintain compatibility with python < 2.7; the code should be compatible with python 3.x, which will be tested in a future upgrade.


Installation
************

There are two recommended approaches to installation and use of dragonfly: docker or virtual environment.
Using docker containers can take more setup but eliminates the need for any installation steps and is useful for integrated development.
The docker approach is preferred for Project 8 collaborators, especially when working within the context of the rest of our controls software ecosystem.
Virtual environments allow for mostly local installation and development; they are common in the python community.

Docker containers
-----------------

The easiest way to get started with docker is simply to use the container image from `DockerHub <https://hub.docker.com/r/project8/dragonfly/>`_.
It's base image chain is dripline-python > python:2.7 > jessie.
Images on DockerHub are automatically built to track tagged versions of the master branch as well as the develop branch.
You may also use the ``Dockerfile`` located in the dragonfly GitHub repository's root directory to build the image yourself (the full repository is the required build context).

Virtual Environments
--------------------

Dragonfly does not exist in PyPI, it is therefore necessary to obtain the source code from GitHub prior to or during installation.
The recommended usage is with a `virtual environment <http://virtualenv.readthedocs.org/en/latest>`_.
Assuming you have virtualenv installed (on debian, you can install it from your package manager; on Mac you should install pip from homebrew, then use pip to instal virtualenv) it is relatively simple to get everything going.
For the complete experience, you would run the following commands to install the local dragonfly source into your virtual environment.

.. code-block:: bash

    $ virtualenv path/to/virt_environments/dragonfly [--system-site-packages]
    $ source path/to/virt_environments/dragonfly/bin/activate
    $ pip install -U pip
    $ pip install ./dragonfly[colorlog]


A few potentially useful notes on installation that are more generic than just dragonfly:

- full functionality of pip may require upgrading to a newer version (``pip install -U pip``)
- the ``extras_require`` in setup.py defines optional dependencies, these can be activated by selecting (a list of) optional dependencies in braces after the package path (``pip install ./dragonfly[colorlog]``)
- install in develop mode to catch local changes to the code with the ``pip install -e`` flag
- install code directly from GitHub without cloning a local copy using ``pip install git+https://github.com/project8/dragonfly#egg=dragonfly[colorlog]``


Python Libraries
****************
There are quite a few dependencies for dragonfly, some required and many optional (though needed for certain features).
Unless otherwise noted, you are encouraged to install any/all of these from PyPI using pip.

Required
--------

`PyYAML <http://pyyaml.org>`_ is used to read yaml formatted configuration files.
It could in principle (and perhaps should) be moved to "optional" status (since it is possible to run several aspects without a config file, and json based config files would be easy to use.
Nevertheless, PyYAML is pervasive and we've had no motivation to refactor to make it cleanly optional.

`asteval <https://newville.github.io/asteval/>`_ is used to process python statements presented as strings (sometimes provided as strings in start-up configurations or as part of calibration definitions).


Optional
--------
Various optional features can be activated by installing one or more extra dependencies.
You may install them directly using pip, or list the optional extras (named in []) when issuing a setuptools install.

Color Output [colorlog]
~~~~~~~~~~~~

`Colorlog <http://pypi.python.org/pypi/colorlog>`_ is completely aesthetic.
The logging module is used throughout dripline and this allows for colorized format of log messages.

Databases [database]
~~~~~~~~~~~~~~~~~~~~

`SQLAlchemy <http://www.sqlalchemy.org>`_ is used to talk to our database.
This is nice because it supports a wide range of databases and backends for them.
In the future, if we elect to change our database, this will hopefully minimize the number of changes we'll need to make.

`psycopg2 <http://initd.org/psycopg>`_ is a PostgreSQL adapter and provides a SQLAlchemy backend by wrapping libpq (the official PostgreSQL client).
Per the `psycopg2 documentation <http://initd.org/psycopg/docs/install.html#installation>`_, you are encouraged to install psycopg2 using your package manager (it should be available from homebrew for Mac users).
If you do so, and are using a virtualenv (and if you're not, why aren't you), you'll need to create your virtualenv with the ``--system-site-packages`` flag, otherwise it won't be found.

Building Docs [doc]
~~~~~~~~~~~~~~~~~~~

`Sphinx <http://sphinx-doc.org/>`_ is required to compile this documentation.

`Sphinx-rdc-theme <https://github.com/snide/sphinx_rtd_theme>`_ is used by Sphinx for a nicer look.

`Sphinx-contrib-programoutput <http://pythonhosted.org/sphinxcontrib-programoutput/>`_ Is used to automatically include the --help for the various utility programs.

Raspberry Pi [gpio or max31856]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`rpi.gpio <https://pypi.python.org/pypi/RPi.GPIO>`_ is used to control (read or write) the GPIO pins on a Raspberry Pi.

`max31856 <https://github.com/johnrbnsn/Adafruit_Python_MAX31856.git>`_ is used to interface with Adafruit Max31856 thermocouple readout.
This is a highly-custom package which allows readout of any thermocouple type with this specific Adafruit board.
Note: This package is not in PyPI and requires a depdency_links or installation by hand!

Slack [slack]
~~~~~~~~~~~~~

`slackclient <https://pypi.python.org/pypi/slackclient>`_ is used to access the Slack API.
Integrate your team Slack with your slow control for posting alarms, status logs, etc.

ROACH DAQ [roach]
~~~~~~~~~~~~~~~~~

Using the ROACH DAQ requires a very specific set of packages with tagged versions.
This is probably more custom than should really exist in dragonfly, but here are the packages:

- `corr==0.7.3 <https://pypi.python.org/pypi/corr/0.7.3>`_
- `katcp==0.5.5 <https://pypi.python.org/pypi/katcp/0.5.5>`_
- `construct==2.5.2 <http://construct.readthedocs.io/en/latest/>`_
- `scipy==0.19.0 <https://www.scipy.org>`_
- `netifaces==0.10.5 <https://pypi.python.org/pypi/netifaces/0.10.5>`_
- `adc5g <https://github.com/sma-wideband/adc_tests.git@65a2ef4e1cf68bee35176a1171d923a73952e13e>`_ Note specific commit! Not available on PyPI!


Helpful Python Packages
~~~~~~~~~~~~~~~~~~~~~~~
The following packages are not actually dependencies for any aspect of dripline.
They are, however, highly recommended (especially for anyone relatively new to python).

`ipython <http://ipython.org>`_ and `ipdb <http://www.pypi.python.org/pypi/ipdb>`_ are both highly recommended for all non-production workflows.
The expanded tab completion, command and output history, and doc access make it a powerful python interpreter for developing or manually interacting with dragonfly components.

`virtualenv <http://virtualenv.readthedocs.org/en/latest>`_ provides a clean way to install python libraries without polluting the system python install (or if you don't have permission to modify the system).
