from __future__ import absolute_import
__all__ = []

# std libraries
import os
import time

# local imports
from dripline.core import Endpoint, exceptions, fancy_doc

import logging
logger = logging.getLogger(__name__)

__all__.append('MdReceiver')

@fancy_doc
class MdReceiver(Endpoint):
    '''
    Base class for mdreceiver
    '''
    def __init__(self,
                 **kwargs):
    '''
    '''
    Endpoint.__init__(self, **kwargs)


    def write_json(self, contents, filename):
        '''
        contents from self._run_meta in DAQProvider
        filename 
        '''
    
        logger.debug('received "write_json" instruction')
        for payload_key in kwargs.keys():
            if not payload_key in set(['contents','filename']):
                raise exceptions.DriplinePayloadError('a value for <{}> is required'.format(payload_key))
        logging.debug("filename to write: {}".format(filename))
        dir_path,_ = os.path.split(filename)
        if not os.path.isdir(folder_in): # check if dir exists
            try: # make directory 
                os.makedirs(dir_path) 
                time.sleep(0.001) # add a small delay after creating the new directory so that anything (e.g. Hornet) 
                                  # waiting for that directory can react to it before the JSON file is created
            except OSError as e:
                logger.error('unable to create directory {}'.format(dir_path))
                raise exceptions.DriplineAccessDenied('directory for metadata unable to be created')
        if not bool(contents):
            logger.error('no file contents present in the message for {}'.format(filaname))
            raise exceptions.DriplineValueError
        contents_json = json.dumps(contents,indent=4,sort_keys=True,separators=(',',':')) # convert to JSON
           
        
        
        
    
