'''
Measures remaining disk space of drives.
'''

from __future__ import absolute_import

import os
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
                 drives_to_check = [],
                 ping_timeout = 10,
                 **kwargs):

        Endpoint.__init__(self,**kwargs)
        Scheduler.__init__(self, **kwargs)
        
        if len(drives_to_check) == 0:
            raise exceptions.DriplineValueError("No entered services to ping")
        self.drives_to_check = drives_to_check
 
        self.connection_to_alert = dirpline.core.Service(broker=broker, exchange='alerts', keys='status_message.#.#')

    def scheduled_action(self):
        '''
        Override Scheduler method with Pinger-specific action
        '''
        logger.info("hello")
        for i in self.drives_to_check:
            disk = os.statvfs(i)
            payload = {}
            payload['val_raw'] = disk.f_bfree*disk.f_bsize
            payload['val_cal'] = disk.f_bfree/disk.f_blocks
            pathway_list = i.split(/)
            machine_name = os.environ['COMPUTERNAME']
            severity = 'sensor_value.disks_' + machine_name + pathway_list[-1]
            self.connection_to_alert.send_alert(severity=severity,alert=payload)        
