#!/usr/bin/python
'''
Script to replace start_node using the spimescape abstraction upgrades
'''

from __future__ import print_function

import imp
import traceback

import dripline

from .. import implementations

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

__all__ = []


__all__.append('Serve')
class Serve(object):
    '''
    start a long-running dripline service based on a provided config file (formerly open_spimescape_portal)
    '''
    name = 'serve'

    def __call__(self, kwargs):
        '''
        '''
        if kwargs.config is None:
            raise KeyError('<config> is required to `dragonfly serve`, use -c flag')
        this_config = vars(kwargs)
        # create the portal:
        if 'module' not in this_config:
            module = dripline.core.Service
        else:
            module = this_config.pop('module')
            module_path = this_config.pop('module_path', False)
            extra_namespace = object()
            if module_path:
                try:
                    extra_namespace = imp.load_source('extra_namespace', module_path)
                except IOError:
                    logger.warning('unable to load source from: {}'.format(module_path))
            if hasattr(extra_namespace, module):
                this_child = getattr(extra_namespace, module)
            elif hasattr(implementations, module):
                module = getattr(implementations, module)
            elif hasattr(dripline.core, module):
                module = getattr(dripline.core, module)
            else:
                raise NameError('no module "{}" in dripline.core or dripline.instruments'.format(module))
        these_endpoints = this_config.pop('endpoints', [])
        service = module(**this_config)
        logger.info('starting {}'.format(service.name))
        ##### need to fix the node class here...
        for provider in these_endpoints:
            service.add_endpoint(self.create_child(service, provider))
        logger.info('spimescapes created and populated')
        logger.info('Configuration of {} complete, starting consumption'.format(service.name))
        try:
            service.start_event_loop()
        except KeyboardInterrupt:
            import threading
            logger.info('there are {} total threads'.format(threading.active_count()))
            for thread in threading.enumerate():
                if thread.name.startswith('logger_'):
                    logger.info('canceling a thread named: {}'.format(thread.name))
                    thread.cancel()
        except Exception as this_exception:
            this_service_name = ''
            try:
                this_service_name = str(service.name)
            except:
                pass
            logger.critical('service <{}> crashing due to unexpected error:\n{}'.format(this_service_name, this_exception))
            logger.error('traceback is:\n{}'.format(traceback.format_exc()))

    def create_child(self, service, conf_dict):
        module = conf_dict.pop('module')
        child_confs = conf_dict.pop('endpoints', [])
        module_path = conf_dict.pop('module_path', False)
        extra_namespace = object()
        if module_path:
            try:
                extra_namespace = imp.load_source('extra_namespace', module_path)
            except IOError:
                logger.warning('unable to load source from: {}'.format(module_path))
        logger.info('creating a <{}> with args:\n{}'.format(module, conf_dict))
        if hasattr(extra_namespace, module):
            this_child = getattr(extra_namespace, module)(**conf_dict)
        elif hasattr(implementations, module):
            this_child = getattr(implementations, module)(**conf_dict)
        elif hasattr(dripline.core, module):
            this_child = getattr(dripline.core, module)(**conf_dict)
        else:
            raise NameError('no module "{}" in dripline.core or dripline.implementations'.format(module))
    
        for child_dict in child_confs:
            this_child.add_endpoint(self.create_child(service, child_dict))
        if isinstance(this_child, dripline.core.Provider):
            for grandchild in this_child.endpoints:
                service.add_endpoint(this_child.endpoints[grandchild])
        return this_child

    def update_parser(self, parser):
        parser.add_argument('-k', '--keys',
                            metavar='BINDING_KEYS',
                            help='amqp binding keys to match against',
                            default='#',
                           )

