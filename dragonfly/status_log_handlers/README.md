This directory is for implementing custom handlers for log messages based on python's internal logging module.

By design, you will be able to simply drop in the source file for a valid handler and add it to the __init__.py file. The logger will then be available with an approprite command line switch to dragonfly.

## Design notes

1. Your handler must be a class which inherits from logging.Handler and your module must name it in the __all__ global variable (which is a list of names).
2. Your handler class must have an attribute named "argparse_flag_str" which is a string which will be prepended with "--" when adding an argument to the base argument parser. (Obviously this must be unique)
3. If your handler has any dependencies which are not standard libraries, you should import them in a try/except block, catching any ImportError. Only add your handler to __all__ if the imports are all successful. This allows your handler to be an optional feature which is available whenever the dependencies are met, without breaking anything if they are not.
4. If your handler requires any password or authentication tokens, consider placing them in ~/.project8_authentications.json, the standard location used by dragonfly.
5. I have not yet determined a standard for allowing users to specify a log level on a per-handler basis, nor is there support for passing in configuration options. This will probably be done by replacing the argparse_flag_str attribute with an update_parser() method which adds an argument to a passed-in parser, allowing a user to configure a flag as taking one or more argument... If someone wanted to implement that it would be super slick.
