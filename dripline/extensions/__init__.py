__path__ = __import__('pkgutil').extend_path(__path__, __name__)

from . import jitter
# add further subdirectories here

import logging
logger = logging.getLogger(__name__)

def __get_version():
    import scarab
    import dragonfly
    import pkg_resources
    #TODO: this all needs to be populated from setup.py and gita
    version = scarab.VersionSemantic()
    logger.info('version should be: {}'.format(pkg_resources.get_distribution('dragonfly').version))
    version.parse(pkg_resources.get_distribution('dragonfly').version)
    version.package = 'project8/dragonfly'
    version.commit = 'na'
    dragonfly.core.add_version('dragonfly', version)
    return version
version = __get_version()
