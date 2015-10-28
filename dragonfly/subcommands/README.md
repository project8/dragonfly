Dragonfly supports adding aribtrary subcommands to the executable.

## How to add a subcommand

1. create a python module in this subdirectory for your implementation, it should contain a class which implements the behavior your want
2. Add your module to the subcommands module by adding two lines to `__init__.py`:
```python
from .<your_module_name_without_extension> import *
__all__ += <your_module_name_without_extension>.__all__
```
3. Your module's class must meet the following structural requirements:
    1. There must be a class attribute `name` with string value; this sets how the subcommand is called from the commandline.
    2. The class must implement method `update_parser` which takes a parser object and uses `parser.add_argument` as needed to add arguments. Whenever reasonable, it is strongly prefered that arguments be keyworded and optional with a sensible default.
    3. The class must implement a `__call__` method. This is the method that will be called by dragonfly, with the entire parsed args namespace passed in as a single argument.
    4. The class should have a `__doc__` attribute, if present it will serve as the content displayed for the command when dragonfly is called with `-h`
