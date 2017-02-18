from setuptools import setup
from glob import glob

import sys
from setuptools.command.test import test as TestCommand

verstr = "none"
try:
    import subprocess
    verstr = subprocess.check_output(['git','describe','--long']).decode('utf-8').strip()
except EnvironmentError:
    pass
except Exception as err:
    print(err)
    verstr = 'v0.0.0-???'


extras_require={
    'colorlog' : ['colorlog'],
    'database': ['psycopg2', 'sqlalchemy'], #this may also require system packages
    'debug': ['ipdb'],
    'doc': ['sphinx', 'sphinx_rtd_theme', 'sphinxcontrib-programoutput'],
    'slack': ['slackclient'],
}
everything = set()
for deps in extras_require.values():
    everything.update(deps)
extras_require['all'] = everything

setup(
    name='dragonfly',
    version=verstr,
    packages=['dragonfly','dragonfly/implementations','dragonfly/status_log_handlers','dragonfly/subcommands'],
    scripts=['bin/dragonfly'],
    install_requires=['dripline', 'asteval'],
    extras_require=extras_require,
    url='http://www.github.com/project8/dragonfly',
)
