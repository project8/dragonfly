#!/usr/bin/python
'''
user documentation and introspection help
'''

from __future__ import absolute_import

import inspect

import logging

import dripline

from .. import implementations

logger = logging.getLogger(__name__)

__all__ = []


__all__.append('DocHelp')
class DocHelp(object):
    '''
    inspect classes and display useful documentation about them
    '''
    name = 'doc'

    def __init__(self):
        self.module_list = [dripline.core, implementations]
        self.module_dict = {}
        for module in self.module_list:
            self.module_dict.update(dict(inspect.getmembers(module, inspect.isclass)))

    def __call__(self, kwargs):
        these_kwargs = kwargs
        action_map = {'children': self.find_children,
                      'help': self.get_docstring,
                     }
        if kwargs.class_name not in self.module_dict:
            print('class <{}> not found in {}'.format(kwargs.class_name, self.module_list))
        else:
            action_map[kwargs.request](kwargs.class_name)

    def find_children(self, class_name):
        children = []
        for name,module in self.module_dict.items():
            if self.module_dict[class_name] in inspect.getmro(module):
                children.append(name)
        if len(children) == 0:
            print('found no children of <{}>'.format(class_name))
        else:
            print('\n'.join(children))

    def get_docstring(self, class_name):
        print(self.module_dict[class_name].__doc__)

    def update_parser(self, parser):
        parser.add_argument('request',
                            choices=['children', 'help'],
                           )
        parser.add_argument('class_name',
                            type=str,
                           )

