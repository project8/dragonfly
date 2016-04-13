# Quick Install

For the sake of an example, I'll assume the following:

1. You've activated the virtualenvironment you want to use
1. You've already installed the dripline in that virtualenv

Simply install all remaining dependencies with pip, and then install dragonfly itself.
```bash
pip install -r requirements.txt
python setup.py install
```

If you will not be interacting with any SQL databases, then you can instead install a reduced set of dependencies.
```bash
pip install -r requirements_no_sql.txt
```
Note: On Claude, use requirements_no_sql.txt