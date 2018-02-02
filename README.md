# Documentation

at http://www.project8.org/dragonfly/

# Quick Install

For the sake of an example, I'll assume the following:

1. You've activated the virtualenvironment you want to use
1. You've already installed the dripline in that virtualenv

Simply use pip to install dragonfly with any desired "extra" dependencies.
```bash
pip install -U pip # pip version >= 7.0.0 required
pip install ${REPOSPATH}/dragonfly[extra1,extra2,...]
```

On claude, the command will be `pip install ~/Repos/dragonfly[colorlog]`, on myrna it will be `pip install ~/Repos/dragonfly[colorlog,database,slack]` to handle the additional services, on zeppelin, it will be `pip install ~/Repos/dragonfly[colorlog,roach]`.

To install in "develop" mode, use `pip install -e` flag.

An alternative is to install directly from github.  See [pip documentation](https://pip.pypa.io/en/stable/reference/pip_install/#git) for details on git+VCS support: branch/commit selection and git+ssh options are also available.
```bash
pip install git+https://github.com/project8/dragonfly#egg=dragonfly[extra1,extra2,...]
```
# Subdirectories
- **dragonfly**: implementations of dripline services, custom log message handlers, extra subcommands for executables 
- **examples**: sample configuration files for different services 
