from __future__ import absolute_import
__all__ = []

# std libraries
import os
import time

# local imports
from dripline.core import Endpoint, exceptions, fancy_doc

import logging
logger = logging.getLogger(__name__)

__all__.append('MDReceiver')

@fancy_doc
class MDReceiver(Endpoint):
    '''
    Base class for mdreceiver
    '''
    def __init__(self,**kwargs):
        Endpoint.__init__(self, **kwargs)


    def write_json(self, contents, filename):
        '''
        contents (dict): dict of metadata to write, keys are e.g 'DAQ','run_time', etc
        filename (str): metadata file name to save including full path
        '''
    
        logger.debug('received "write_json" instruction')
        logging.debug('filename to write: <{}>'.format(filename))
        dir_path,_ = os.path.split(filename)

        if not os.path.isdir(dir_path): # check if dir exists, if not then create it 
            try: # make directory 
                os.makedirs(dir_path) 
                time.sleep(0.001) # add a small delay after creating the new directory so that anything (e.g. Hornet) 
                                  # waiting for that directory can react to it before the JSON file is created
            except OSError as e:
                logger.error('unable to create metadata directory')
                raise exceptions.DriplineHardwareError('directory for metadata <{}> unable to be created: {}'.format(dir_path,e))

        if not bool(contents): # check if contents are present in the message
            logger.error('no file contents present in the message for {}'.format(filename))
            raise exceptions.DriplinePayloadError('contents dictionary of metadata payload is empty')

        try: # convert file contents to JSON
            contents_json = json.dumps(contents,indent=4,sort_keys=True,separators=(',',':'))
        except Exception as e:
            logger.error('unable to dump metadata contents to JSON format')
            raise exceptions.DriplinePayloadError('metadata file failed conversion to JSON: {}'.format(e))

        if not os.path.isfile(filename): # if file doesn't exist
            f = open(filename,'w') # create it 
            f.write(contents_json) # write it
            f.close()
        else:
            logger.error('<{}> already exists'.format(filename))
            raise exceptions.DriplineHardwareError('unable to create <{}> since it already exists'.format(filename))

        logger.info('File written: <{}>'.format(filename))
           
        return 
