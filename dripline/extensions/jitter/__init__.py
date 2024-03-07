__all__ = []

import pkg_resources

import scarab
a_ver = '0.0.0' #note that this is updated in the following block
try:
    a_ver = pkg_resources.get_distribution('dragonfly').version
    print('version is: {}'.format(a_ver))
except:
    print('fail!')
    pass
version = scarab.VersionSemantic()
version.parse(a_ver)
version.package = 'project8/dragonfly'
version.commit = '---'
__all__.append("version")

from .jitter_endpoint import *
from .jitter_endpoint import __all__ as __jitter_all
__all__ += __jitter_all

