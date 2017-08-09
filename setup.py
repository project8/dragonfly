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
    'max31856': ['adafruit_max31856','rpi.gpio'], #only for RPi
    'roach': ['corr==0.7.3','katcp==0.5.5','construct==2.5.2','scipy==0.19.0','netifaces==0.10.5','adc5g==0.0.1'],
    'gpio': ['rpi.gpio'], #only for RPi
    'slack': ['slackclient']
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
    dependency_links=['git+https://github.com/sma-wideband/adc_tests.git@65a2ef4e1cf68bee35176a1171d923a73952e13e#egg=adc5g-0.0.1',
                      'git+https://github.com/johnrbnsn/Adafruit_Python_MAX31856.git#egg=adafruit_max31856-0.0.1'],
    extras_require=extras_require,
    url='http://www.github.com/project8/dragonfly',
)
