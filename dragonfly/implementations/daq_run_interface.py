'''
A service for uniform interfacing with the DAQ (in general)
'''

from __future__ import absolute_import


# standard imports
import logging
import uuid
import time
import os
import json
from datetime import datetime

# internal imports
from dripline import core

__all__ = []

logger = logging.getLogger(__name__)

__all__.append('DAQProvider')

@core.fancy_doc
class DAQProvider(core.Provider):
    '''
    Base class for providing a uniform interface to different DAQ systems
    '''
    def __init__(self,
                 daq_name=None,
                 run_table_endpoint=None,
                 directory_path=None,
                 data_directory_path=None,
                 meta_data_directory_path=None,
                 filename_prefix='',
                 snapshot_state_target='',
                 metadata_state_target='',
                 metadata_target='',
                 set_condition_list = [10],
                 **kwargs):
        '''
        daq_name (str): name of the DAQ (used with the run table and in metadata)
        run_table_endpoint (str): name of the endpoint providing an interface to the run table
        directory_path (str): absolute path to "hot" storage (as seen from the DAQ software, not a network path)
        meta_data_directory_path (str): path where the metadata file should be written
        filename_prefix (str): prefix for unique filenames
        snapshot_state_target (str): target to request snapshot from
        metadata_state_target (str): multiget endpoint to Get() for system state
        metadata_target (str): target to send metadata to
        '''
        core.Provider.__init__(self, **kwargs)

        if daq_name is None:
            raise core.exceptions.DriplineValueError('<{}> instance <{}> requires a value for "{}" to initialize'.format(self.__class__.__name__, self.name, 'daq_name'))
        else:
            self.daq_name = daq_name
        if run_table_endpoint is None:
            raise core.exceptions.DriplineValueError('<{}> instance <{}> requires a value for "{}" to initialize'.format(self.__class__.__name__, self.name, 'run_table_endpoint'))
        else:
            self.run_table_endpoint = run_table_endpoint

        # deal with directory structures
        if (directory_path is None) and (data_directory_path is None) and (meta_data_directory_path is None):
            raise core.exceptions.DriplineValueError('<{}> instance <{}> requires a value for "{}" to initialize'.format(self.__class__.__name__, self.name, '[meta_[data_]]directory_path'))
        if (data_directory_path is None) and (directory_path is not None):
            data_directory_path = directory_path
        if (meta_data_directory_path is None) and (directory_path is not None):
            meta_data_directory_path = directory_path
        self.data_directory_path = data_directory_path
        self.meta_data_directory_path = meta_data_directory_path

        self._metadata_state_target = metadata_state_target
        self._metadata_target = metadata_target
        self._snapshot_state_target = snapshot_state_target
        self.filename_prefix = filename_prefix

        self._stop_handle = None
        self._run_name = None
        self.run_id = None
        self._start_time = None
        self._start_time = None
        self._run_meta = None
        self._run_snapshot = None
        self._run_time = None

        # Set condition and DAQ safe mode init
        self._daq_in_safe_mode = False
        self._set_condition_list = set_condition_list

    @property
    def run_name(self):
        return self._run_name
    @run_name.setter
    def run_name(self, value):
        ''' inserts run name to run table in database and retrieves run id and start timestamp

        value (str): name of acquisition run
        '''
        self._run_name = value
        try:
            result = self.provider.cmd(self.run_table_endpoint, 'do_insert', payload={'run_name':value})
            self.run_id = result['run_id']
            self._start_time = result['start_timestamp']
        except Exception as err:
            if self._stop_handle is not None:  # end the run
                self.service._connection.remove_timeout(self._stop_handle)
                self._stop_handle = None
                self._run_name = None
                self.run_id = None
            raise core.exceptions.DriplineValueError('failed to insert run_name to the db, obtain run_id, and start_timestamp. run "<{}>" not started\nerror:\n{}'.format(value,str(err)))

    def start_run(self, run_name):
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

    def end_run(self):
        '''
        Send command to the DAQ provider to stop data taking, do the post-run snapshot, and announce the end of the run.
        '''
        # call _stop_data_taking DAQ-specific method
        self._stop_data_taking()

        if self._stop_handle is not None:
            logger.info("Removing sec timeout for run <{}> duration".format(self.run_id))
            self.service._connection.remove_timeout(self._stop_handle)
            self._stop_handle = None
        if self.run_id is None:
            raise core.exceptions.DriplineValueError("No run to end: run_id is None.")
        self._do_snapshot()
        logger.info('run <{}> ended'.format(self.run_id))
        self._run_name = None
        self.run_id = None

    def _do_prerun_gets(self):
        '''
        Calls pre-run methods to obtain run metadata
        '''
        logger.info('doing prerun meta-data get')
        meta_result = self.provider.get(self._metadata_state_target, timeout=30)
        self._run_meta.update(meta_result['value_raw'])
        self.determine_RF_ROI()

    def _do_snapshot(self):
        '''
        Calls take_snapshot method of snapshot target for database snapshot
        '''
        logger.info('requesting snapshot of database')
        filename = '{directory}/{runNyx:03d}yyyxxx/{runNx:06d}xxx/{runN:09d}/{prefix}{runN:09d}_snapshot.json'.format(
                                                                   directory=self.meta_data_directory_path,
                                                                   prefix=self.filename_prefix,
                                                                   runNyx=self.run_id/1000000,
                                                                   runNx=self.run_id/1000,
                                                                   runN=self.run_id
                                                                  )
        time_now = datetime.utcnow().strftime(core.constants.TIME_FORMAT)
        snap_state = self.provider.cmd(self._snapshot_state_target,'take_snapshot',[self._start_time,time_now,filename],timeout=30)
        logger.info('snapshot returned ok')

    def determine_RF_ROI(self):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement RF ROI determination')

    def _send_metadata(self):
        '''
        Sends metadata to metadata target (mdreceiver) to be written to file(s)
        '''
        logger.info('metadata should broadcast')
        filename = '{directory}/{runNyx:03d}yyyxxx/{runNx:06d}xxx/{runN:09d}/{prefix}{runN:09d}_meta.json'.format(
                                                                    directory=self.meta_data_directory_path,
                                                                    prefix=self.filename_prefix,
                                                                    runNyx=self.run_id/1000000,
                                                                    runNx=self.run_id/1000,
                                                                    runN=self.run_id
                                                                   )
        this_payload = {'contents': self._run_meta,
                        'filename': filename,
                       }
        this_payload['contents']['run_id'] = self.run_id
        # note, the following line has an empty method/RKS, this shouldn't be the case but is what golang expects
        req_result = self.provider.cmd(self._metadata_target, 'write_json', payload=this_payload)
        logger.debug('meta sent')

    def start_timed_run(self, run_name, run_time):
        '''
        Starts timed acquisition run
        run_name (str): name of acquisition run
        run_time (int): length of run in seconds
        '''
        self._run_time = int(run_time)
        if self._daq_in_safe_mode:
            logger.info("DAQ in safe mode")
            raise core.exceptions.DriplineDAQNotEnabled("{} is not enabled: enable it using <dragonfly cmd broadcast.set_condition 0 -b myrna.p8>".format(self.daq_name))

        logger.debug('testing if the DAQ is running')
        result = self.is_running
        if result == True:
            raise core.exceptions.DriplineDAQRunning('DAQ is already running: aborting run')

        # do the last minutes checks: DAQ specific
        self._do_checks()

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
        self._start_data_taking(directory,filename)
        logger.info("Adding {} sec timeout for run <{}> duration".format(self._run_time, self.run_id))
        self._stop_handle = self.service._connection.add_timeout(self._run_time, self.end_run)
        return self.run_id

    @property
    def is_running(self):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement is running method')

    def _do_checks(self):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement checks methods')

    def _start_data_taking(self,directory,filename):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement start data taking method')

    def _stop_data_taking(self):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement stop data taking method')

    def _set_condition(self,number):
        '''
        Puts/Removes DAQ in safe mode
        number (int): 0 (leave safe mode) or e.g 10 for global DAQ stop or 11 for RSA DAQ stop
        '''
        logger.debug('receiving a set_condition {} request'.format(number))
        if number in self._set_condition_list:
            logger.debug('putting myself in safe_mode')
            self._daq_in_safe_mode = True
            logger.critical('Condition {} reached!  DAQ in safe mode!'.format(number))
        elif number == 0:
            logger.debug('getting out of safe_mode')
            self._daq_in_safe_mode = False
            logger.critical('Condition {} reached!  Not in safe mode.'.format(number))
        else:
            logger.debug('condition {} is unknown: ignoring!'.format(number))
