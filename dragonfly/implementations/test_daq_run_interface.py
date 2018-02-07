'''
A service to test interfacing with a general DAQ
'''

from __future__ import absolute_import


# standard imports
import logging

# internal imports
from dripline import core

__all__ = []

logger = logging.getLogger(__name__)

__all__.append('TestingDAQProvider')
@core.fancy_doc
class TestingDAQProvider(DAQProvider):
    '''
    A class for testing a minimal DAQProvider, e.g in insectarium
    '''
    def __init__(self,
                 **kwargs):
        DAQProvider.__init__(self,**kwargs)

    def _do_prerun_gets(self):
        '''
        Calls pre-run methods to obtain run metadata
        '''
        logger.info('doing prerun meta-data get')
        meta_result = self.provider.get(self._metadata_state_target, timeout=30)
        self._run_meta.update(meta_result['value_raw'])

    def start_run(self,run_name):
        '''
        Do the prerun_gets and send the metadata to the recording associated computer
        
        run_name (str): name of acquisition run
        '''
        self.run_name = run_name
        self._run_meta = {'DAQ': self.daq_name,
                          'run_time': self._run_time,
                         }
        self._do_prerun_gets()
        self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')
    
    def start_timed_run(self, run_name, run_time):
        '''
        Starts timed acquisition run 

        run_name (str): name of acquisition run
        run_time (int): length of run in seconds
        '''
        self._run_time = int(run_time)

        # get run_id and do pre_run gets
        self.start_run(run_name)

        # call start_run method in daq_target
        directory = '{base}/{runNyx:03d}yyyxxx/{runNx:06d}xxx/{runN:09d}'.format(
                                                                    base=self.data_directory_path,
                                                                    runNyx=self.run_id/1000000,
                                                                    runNx=self.run_id/1000,
                                                                    runN=self.run_id
                                                                   )

        filename = "{}{:09d}".format(self.filename_prefix, self.run_id)
        logger.info("Adding {} sec timeout for run <{}> duration".format(self._run_time, self.run_id))
        self._stop_handle = self.service._connection.add_timeout(self._run_time, self.end_run)
        return self.run_id

    def end_run(self):
        '''
        Send command to stop data taking, do the post-run snapshot, and announce the end of the run
        '''
        if self._stop_handle is not None:
            logger.info("Removing sec timeout for run <{}> duration".format(self.run_id))
            self.service._connection.remove_timeout(self._stop_handle)
        if self.run_id is None:
            raise core.exceptions.DriplineValueError("No run to end: run_id is None.")
        self._do_snapshot()
        run_was = self.run_id
        self._run_name = None
        self.run_id = None
        logger.info('run <{}> ended'.format(run_was))    
