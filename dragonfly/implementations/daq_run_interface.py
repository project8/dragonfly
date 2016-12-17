'''
'''

from __future__ import absolute_import

# standard imports
import logging
import json
from datetime import datetime

# internal imports
from dripline import core

__all__ = []

logger = logging.getLogger(__name__)

__all__.append('DAQProvider')
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
                 snapshot_target_items=None,
                 metadata_state_target='',
                 metadata_target='',
                 **kwargs):
        '''
        daq_name (str): name of the DAQ (used with the run table and in metadata)
        run_table_endpoint (str): name of the endpoint providing an interface to the run table
        directory_path (str): absolute path to "hot" storage (as seen from the DAQ software, not a network path)
        meta_data_directory_path (str): path where the metadata file should be written
        filename_prefix (str): prefix for unique filenames
        snapshot_target_items (dict): keys are SQLSnapshot table endpoint names, values are lists of items (str) to take snapshot of
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
        self._snapshot_target_items = snapshot_target_items
        self._metadata_target = metadata_target
        self.filename_prefix = filename_prefix

        self._stop_handle = None
        self._run_name = None
        self.run_id = None
        self._start_time = None
        self._acquisition_count = None
        self._start_time = None
        self._run_meta = None
        self._run_snapshot = None
        self._run_time = None

    @property
    def run_name(self):
        return self._run_name
    @run_name.setter
    def run_name(self, value):
        self._run_name = value
        self._acquisition_count = 0
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

    def end_run(self):
#        self._do_postrun_gets()
#        self._send_snapshot()
        run_was = self.run_id
        if self._stop_handle is not None:
            self.service._connection.remove_timeout(self._stop_handle)
            self._stop_handle = None
        self._run_name = None
        self.run_id = None
        logger.info('run <{}> ended'.format(run_was))

    def start_run(self, run_name):
        '''
        '''
        self.run_name = run_name
        self._run_meta = {'DAQ': self.daq_name,
                          'run_time': self._run_time,
                         }
        self._run_snapshot = {'LATEST':{},'LOGS':{}}
        self._do_prerun_gets()
        self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')

    def _do_prerun_gets(self):
        logger.info('doing prerun meta-data and snapshot gets')
        meta_result = self.provider.get(self._metadata_state_target, timeout=30)
        self._run_meta.update(meta_result['value_raw'])
#        for target,item_list in self._snapshot_target_items.items():
#            snapshot_result = self.provider.cmd(target, 'get_latest', [self._start_time,item_list], timeout=30)
#            these_snaps = snapshot_result['value_raw']
#            self._run_snapshot['LATEST'].update(these_snaps)
        self.determine_RF_ROI()

    def _do_postrun_gets(self):
        logger.info('doing postrun snapshot gets')
        time_now = datetime.utcnow().strftime(core.constants.TIME_FORMAT)
        for target in self._snapshot_target_items:
            snapshot_result = self.provider.cmd(target, 'get_logs', [self._start_time,time_now], timeout=30)
            these_snaps = snapshot_result['value_raw']
            self._run_snapshot['LOGS'].update(these_snaps)

    def determine_RF_ROI(self):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement RF ROI determination')

    def _send_metadata(self):
        '''
        '''
        logger.info('metadata should broadcast')
        filename = '{directory}/{runN:09d}/{prefix}{runN:09d}_meta.json'.format(
                                                        directory=self.meta_data_directory_path,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id,
                                                        acqN=self._acquisition_count
                                                                               )
        logger.debug('should request metadatafile: {}'.format(filename))
        this_payload = {'contents': self._run_meta,
                        'filename': filename,
                       }
        this_payload['contents']['run_id'] = self.run_id
        # note, the following line has an empty method/RKS, this shouldn't be the case but is what golang expects
        req_result = self.provider.cmd(self._metadata_target, None, payload=this_payload)
        logger.debug('meta sent')

    def _send_snapshot(self):
        '''
        '''
        logger.info('snapshot of the slow control database should broadcast')
        filename = '{directory}/{runN:09d}/{prefix}{runN:09d}_snapshot.json'.format(
                                                        directory=self.meta_data_directory_path,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id,
                                                        acqN=self._acquisition_count
                                                                                )
        logger.debug('should request snapshot file: {}'.format(filename))
        this_payload = {'contents': self._run_snapshot,
                        'filename': filename}
        req_result = self.provider.cmd(self._metadata_target, None, payload=this_payload)
        logger.debug('snapshot sent')

    def start_timed_run(self, run_name, run_time):
        '''
        '''
        self._run_time = int(run_time)
        self._stop_handle = self.service._connection.add_timeout(self._run_time, self.end_run)
        self.start_run(run_name)
        return self.run_id


__all__.append('RSAAcquisitionInterface')
class RSAAcquisitionInterface(DAQProvider):
    '''
    A DAQProvider for interacting with the RSA
    '''
    def __init__(self,
                 daq_target=None,
                 hf_lo_freq=None,
                 instrument_setup_filename_prefix=None,
                 mask_filename_prefix=None,
                 trace_path=None,
                 trace_metadata_path=None,
                 metadata_endpoints=None,
                 set_condition_list = [10],
                 **kwargs):
        DAQProvider.__init__(self, **kwargs)

        if daq_target is None:
            raise core.exceptions.DriplineValueError('the rsa acquisition interface requires a valid "daq_target" in its config file')
        self._daq_target = daq_target
        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the rsa acquisition interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq

        if isinstance(trace_path,str):
            if trace_path.endswith("/"):
                self.trace_path = trace_path
            else:
                self.trace_path = trace_path + "/"
        else:
            logger.info("No trace_path given in the config file: save_trace feature disabled")
            self.trace_path = None
        if isinstance(trace_metadata_path,str):
            if trace_metadata_path.endswith("/"):
                self.trace_metadata_path = trace_metadata_path
            else:
                self.trace_metadata_path = trace_metadata_path + "/"
        else:
            self.trace_metadata_path = None
        self._metadata_endpoints = metadata_endpoints

        self._daq_in_safe_mode = False
        self._set_condition_list = set_condition_list

        # naming prefixes are not currently implemented, but maintained in code for consistency
        #self.instrument_setup_filename_prefix = instrument_setup_filename_prefix
        #self.mask_filename_prefix = mask_filename_prefix

    @property
    def is_running(self):
        if self._daq_in_safe_mode is True:
            return 2 #can be a sentence
        result = self.provider.get("rsa_trigger_status")
        logger.info('RSA trigger status is <{}>'.format(result['value_cal']))
        return bool(int(result['value_raw'])) # should either 0 or 1, can be a sentence

    def start_run(self, run_name):

        logger.debug('testing if the DAQ is running')
        result = self.is_running
        if result == 1:
            raise core.exceptions.DriplineHardwareError('RSA is already running: aborting run')
        if result == 2:
            raise core.exceptions.DriplineHardwareError('RSA is in safe mode: remove it from there with <dragonfly cmd broadcast.set_condition 0 -b myrna.p8>')
        # try to force external reference
        the_ref = self.provider.set('rsa_osc_source', 'EXT')['value_raw']
        if the_ref != 'EXT':
            raise core.exceptions.DriplineHardwareError('RSA external ref found to be <{}> (!="EXT")'.format(the_ref))

        # counting the number of errors in the RSA system queue and aborting the data taking if Nerrors>0
        Nerrors = self.provider.get('rsa_system_error_count')['value_raw']
        if Nerrors != '0':
            raise core.exceptions.DriplineHardwareError('RSA system has {} error(s) in the queue: check them with <dragonfly get rsa_system_error_queue -b myrna.p8>'.format(Nerrors))

        super(RSAAcquisitionInterface, self).start_run(run_name)

        # call start_run method in daq_target
        directory = "\\".join([self.data_directory_path, '{:09d}'.format(self.run_id)])
        filename = "{}{:09d}".format(self.filename_prefix, self.run_id)
        self.provider.cmd(self._daq_target, 'start_run', [directory, filename])

    def end_run(self):
        # call end_run method in daq_target
        self.provider.cmd(self._daq_target, 'end_run')
        # call global DAQ end_run method
        super(RSAAcquisitionInterface, self).end_run()

    def determine_RF_ROI(self):
        logger.info('trying to determine roi')

        self._run_meta['RF_HF_MIXING'] = float(self._hf_lo_freq)
        logger.debug('RF High stage mixing: {}'.format(self._run_meta['RF_HF_MIXING']))

        result = self.provider.get('rsa_min_frequency')['value_raw']
        self._run_meta['RF_ROI_MIN'] = float(result) + float(self._hf_lo_freq)
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

        result = self.provider.get('rsa_max_frequency')['value_raw']
        self._run_meta['RF_ROI_MAX'] = float(result) + float(self._hf_lo_freq)
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))

    def save_trace(self, trace, comment):
        if self.trace_path is None:
            raise DriplineValueError("No trace_path in RSA config file: save_trace feature disabled!")

        if isinstance(comment,(str,unicode)):
            comment = comment.replace(" ","_")
        datenow = datetime.now()
        filename = "{:%Y%m%d_%H%M%S}/{:%Y%m%d_%H%M%S}_Trace{}_{}".format(datenow,datenow,trace,comment)

        logger.info('saving trace')
        path = self.trace_path + "{}_data".format(filename)
        self.provider.cmd('rsa_interface','_save_trace',[trace,path])
        logger.info("saving {}: successful".format(path))

        if self.trace_metadata_path is None:
            raise DriplineValueError("No trace_metadata_path in RSA config file: metadata save disabled!")
        result_meta = {}
        if isinstance(self._metadata_endpoints,list):
            for endpoint_name in self._metadata_endpoints:
                result_meta.update(self.provider.get(endpoint_name,timeout=100)['value_raw'])
                logger.debug("getting {} endpoint: successful".format(endpoint_name))
        elif isinstance(self._metadata_endpoints,str):
            result_meta.update(self.provider.get(self._metadata_endpoints,timeout=100)['value_raw'])
            logger.debug("getting {} endpoint: successful".format(self._metadata_endpoints))
        else:
            raise DriplineValueError("No valid metadata_endpoints in RSA config.")

        path = self.trace_metadata_path + "{}_metadata.json".format(filename)
        logger.debug("opening file")
        with open(path, "w") as outfile:
            logger.debug("things are about to be dumped in file")
            json.dump(result_meta, outfile, indent=4)
            logger.debug("things have been dumped in file")
        logger.info("saving {}: successful".format(path))

    def _set_condition(self,number):
        logger.debug('receiving a set_condition {} request'.format(number))
        if number in self._set_condition_list:
            logger.debug('putting myself in safe_mode')
            self._daq_in_safe_mode = True
            logger.critical('Condition {} reached!'.format(number))
        elif number == 0:
            logger.debug('getting out of safe_mode')
            self._daq_in_safe_mode = False
            logger.critical('Condition {} reached!'.format(number))
        else:
            logger.debug('condition {} is unknown: ignoring!'.format(number))
