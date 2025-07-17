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
__version__ = version.version

from .watchdog import *
