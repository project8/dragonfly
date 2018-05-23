'''
Measures remaining disk space of drives.
'''

from __future__ import absolute_import

import shutil
import logging
logger=logging.getLogger(__name__)

from dripline.core import Endpoint, exceptions, Scheduler, fancy_doc

__all__ = []
__all__.append('Diopsid')
@fancy_doc
class Diopsid(Endpoint,Scheduler):
    '''

    '''
    def __init__(self,
                 services_to_ping = [],
                 ping_timeout = 10,
                 **kwargs):

        Endpoint.__init__(self,**kwargs)
        Scheduler.__init__(self, **kwargs)
        
        if len(services_to_ping) == 0:
            raise exceptions.DriplineValueError("No entered services to ping")
        self.services_to_ping = services_to_ping
 

    def scheduled_action(self):
        '''
        Override Scheduler method with Pinger-specific action
        '''
        logger.info("hello")
        return_dict = {}
        for i in self.services_to_ping:
            disk = shutil.disk_usage(i)
            payload = {}
            payload['val_raw'] = disk[2]/1024/1024/1024
            payload['val_cal'] = disk[2]/disk[0]
            return_dict.update({i: payload})
        return return_dict
