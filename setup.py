from setuptools import setup, find_namespace_packages

packages = find_namespace_packages('.', include=['dragonfly', 'dripline.extensions', 'dripline.extensions.*'])
print('packages are: {}'.format(packages))

setup(
    name="dragonfly",
    version='v2.1.1',  # TODO: should get version from git
    packages=packages,
)
