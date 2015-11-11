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
    'doc': ['sphinx', 'sphinx_rtd_theme', 'sphinxcontrib-programoutput'],
    'database': ['cython', 'psycopg2', 'sqlalchemy'], #this may also require system packages
    'slack': ['slackclient'],
    'dpph': ['numpy'],
    'other': ['colorlog', 'ipython', 'ipdb'],
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
    install_requires=['dripline>=v3.0.0'],
    extras_require=extras_require,
    url='http://www.github.com/project8/dragonfly',
)
