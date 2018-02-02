This directory is for implementing custom service modules for varying applications. These include device interfacing, monitoring, database interaction, etc

## How to add a module

1. Create a python module in this directory for your implementation, it should contain a class which implements the behavior your want
2. Use the `@fancy_doc` decorator for your class:
      ```python
      @fancy_doc
      class <your_class_name>():
      ```
3. Add your module to the package by adding:
  - To your python module script:
      ```python
      __all__ = []
      __all__.append('<your_class_name>')
      ```
  - To `__init__.py`:
      ```python
      from .<your_module_name_without_extension> import *
    ```
    Keep it in alphabetical sequence unless otherwise noted.
