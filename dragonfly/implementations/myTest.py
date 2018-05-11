'''
Ping on a regular basis a list of endpoints
'''

from __future__ import absolute_import

import logging
logger=logging.getLogger(__name__)

from dripline.core import Endpoint, Scheduler, fancy_doc

__all__ = []
__all__.append('MyTest')
@fancy_doc
class MyTest(Endpoint,Scheduler):
    '''

    '''
    def __init__(self,
                 services_to_ping = [],
                 ping_timeout = 10,
                 **kwargs):

        Endpoint.__init__(self,**kwargs)
        Scheduler.__init__(self, **kwargs)

 

    def scheduled_action(self):
        '''
        Override Scheduler method with Pinger-specific action
        '''
        print("hello")