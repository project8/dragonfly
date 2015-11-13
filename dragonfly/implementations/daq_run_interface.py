'''
'''

from __future__ import absolute_import

# standard imports
import logging
import uuid

# internal imports
from dripline import core
from .ethernet_provider import EthernetProvider

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
                 ensure_sets={},
                 ensure_locked=[],
                 metadata_gets={},
                 metadata_target=None,
                 debug_mode_without_database=False,
                 debug_mode_without_metadata_broadcast=False,
                 **kwargs):
        '''
        daq_name (str): name of the DAQ (used with the run table and in metadata)
        run_table_endpoint (str): name of the endpoint providing an interface to the run table
        directory_path (str): absolute path to "hot" storage (as seen from the DAQ software, not a network path)
        ensure_sets (dict): a dictionary of endpoint names as keys, with values to set them to. These will all be set prior to each run and should 
        filename_prefix (str): string which will prefix unique filenames
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
        #self.directory_path = directory_path
        self.data_directory_path = data_directory_path
        self.meta_data_directory_path = meta_data_directory_path
        
        self._ensure_sets = ensure_sets
        self._ensure_locked = ensure_locked
        self._metadata_gets = metadata_gets
        self._metadata_target = metadata_target
        self.filename_prefix = filename_prefix
        self._debug_without_db = debug_mode_without_database
        self._debug_without_meta_broadcast = debug_mode_without_metadata_broadcast

        self._stop_handle = None
        self._run_name = None
        self.run_id = None
        self._acquisition_count = None
        self._internal_lockout_key = None

    @property
    def run_name(self):
        return self._run_name
    @run_name.setter
    def run_name(self, value):
        self._run_name = value
        self._acquisition_count = 0
        if self._debug_without_db:
            logger.debug('not going to try to talk to database')
            self.run_id = 0
            return
        request = core.RequestMessage(msgop=core.OP_CMD,
                                      payload={'values':['do_insert'],
                                               'run_name':value,
                                              },
                                     )
        result = self.portal.send_request(self.run_table_endpoint,
                                          request=request,
                                         )
        self.run_id = result.payload['run_id']

    def end_run(self):
        run_was = self.run_id
        if self._stop_handle is not None:
            self.portal._connection.remove_timeout(self._stop_handle)
            self._stop_handle = None
        self._run_name = None
        self.run_id = None
        logger.info('run <{}> ended'.format(run_was))
    
    def start_run(self, run_name):
        '''
        '''
        self.run_name = run_name
        self._do_prerun_sets()
        actually_locked = self._do_prerun_lockout()
        logger.debug('will need to unlock: {}'.format(actually_locked))
        self._run_meta = {'DAQ': self.daq_name,
                         }
        self._do_prerun_gets()
        if not self._debug_without_meta_broadcast:
            self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')

    def _do_prerun_sets(self):
        logger.info('doing prerun sets')
        m = core.RequestMessage(msgop=core.OP_SET, payload={'values':[None]})
        if self._internal_lockout_key:
            m.lockout_key = self._internal_lockout_key
        for endpoint,value in self._ensure_sets.items():
            logger.debug('should set {} -> {}'.format(endpoint,value))
            m.payload['values'] = [value]
            result = self.portal.send_request(request=m, target=endpoint)
            if result.retcode != 0:
                raise core.exception_map[result.retcode](result.return_msg)
        logger.debug('prerun sets complete')
    
    def _do_prerun_lockout(self):
        logger.info('doing prerun lockout')
        this_lockout_key = self._internal_lockout_key or self.lockout_key or uuid.uuid4().get_hex()
        self._internal_lockout_key = this_lockout_key
        to_unlock = []
        lock_query = core.RequestMessage(msgop=core.OP_GET)
        lock_cmd = core.RequestMessage(msgop=core.OP_CMD, lockout_key=this_lockout_key)
        for endpoint in self._ensure_locked:
            logger.debug('ensuring lockout of {}'.format(endpoint))
            if not self.portal.send_request(request=lock_query, target=endpoint+'.is-locked').payload['values'][0]:
                self.portal.send_request(request=lock_cmd, target=endpoint+'.lock')
                to_unlock.append(endpoint)
        logger.debug('prerun lockout complete')
        return to_unlock

    def _do_prerun_gets(self):
        logger.info('doing prerun meta-data gets')
        query_msg = core.RequestMessage(msgop=core.OP_GET)
        these_metadata = {}
        for endpoint,element in self._metadata_gets.items():
            result = self.portal.send_request(request=query_msg, target=endpoint)
            these_metadata[endpoint] = result.payload[element]
        self._run_meta.update(these_metadata)
        self.determine_RF_ROI()

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
        logger.warning('should request metadatafile: {}'.format(filename))
        this_payload = {'metadata': self._run_meta,
                        'filename': filename,
                       }
        this_payload['metadata']['run_id'] = self.run_id
        request_msg = core.RequestMessage(payload=this_payload, msgop=core.OP_CMD)
        req_result = self.portal.send_request(request=request_msg, target=self._metadata_target)
        if not req_result.retcode == 0:
            raise core.exceptions.DriplineValueError('writing meta-data did not return success')
        logger.debug('meta sent')

    def start_timed_run(self, run_name, run_time):
        '''
        '''
        self._stop_handle = self.portal._connection.add_timeout(int(run_time), self.end_run)
        self.start_run(run_name)


__all__.append('MantisAcquisitionInterface')
class MantisAcquisitionInterface(DAQProvider, core.Spime):
    '''
    A DAQProvider for interacting with Mantis DAQ
    '''
    def __init__(self,
                 mantis_queue='mantis',
                 lf_lo_endpoint_name=None,
                 hf_lo_freq=24.2e9,
                 analysis_bandwidth=50e6,
                 #filename_prefix='',
                 **kwargs
                ):
        '''
        mantis_queue (str): binding key for mantis AMQP service
        lf_lo_endpoint_name (str): endpoint name for the 2nd stage LO
        hf_lo_freq (float): local oscillator frequency [Hz] for the 1st stage (default should be correct)
        analysis_bandwidth (float): total receiver bandwidth [Hz]
        '''
        DAQProvider.__init__(self, **kwargs)
        core.Spime.__init__(self, **kwargs)
        self.alert_routing_key = 'daq_requests'
        self.mantis_queue = mantis_queue
        #self.filename_prefix = filename_prefix
        if lf_lo_endpoint_name is None:
            raise core.exceptions.DriplineValueError('the mantis interface requires a "lf_lo_endpoint_name"')
        self._lf_lo_endpoint_name = lf_lo_endpoint_name
        self._hf_lo_freq = hf_lo_freq
        self._analysis_bandwidth = analysis_bandwidth

    @property
    def acquisition_time(self):
        return self.log_interval
    @acquisition_time.setter
    def acquisition_time(self, value):
        self.log_interval = value

    def start_run(self, run_name):
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[self.acquisition_time*1000.]}), target=self.mantis_queue+'.duration')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        super(MantisAcquisitionInterface, self).start_run(run_name)
        self.on_get()
        self.logging_status = 'on'

    def start_timed_run(self, run_name, run_time):
        '''
        '''
        super(MantisAcquisitionInterface, self).start_run(run_name)
        num_acquisitions = int(run_time // self.acquisition_time)
        last_run_time = run_time % self.acquisition_time
        logger.info("going to request <{}> runs, then one of <{}> [s]".format(num_acquisitions, last_run_time))
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[self.acquisition_time*1000]}), target=self.mantis_queue+'.duration')
        if result.retcode != 0:
            logger.warning('bad set')
        for acq in range(num_acquisitions):
            self.on_get()
        if last_run_time != 0:
            self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[last_run_time*1000]}), target=self.mantis_queue+'.duration')
            self.on_get()
            self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[self.acquisition_time*1000]}), target=self.mantis_queue+'.duration')

    def determine_RF_ROI(self):
        logger.info('trying to get roi')
        if not self._lf_lo_endpoint_name in self._run_meta:
            logger.error('meta are:\n{}'.format(self._run_meta))
            raise core.exceptions.DriplineInternalError('the lf_lo_endpoint_name must be configured in the metadata_gets field')
        lf_lo_freq = self._run_meta.pop(self._lf_lo_endpoint_name)
        self._run_meta['RF_ROI_MIN'] = lf_lo_freq + self._hf_lo_freq
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))
        self._run_meta['RF_ROI_MAX'] = self._analysis_bandwidth + lf_lo_freq + self._hf_lo_freq
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))

    def on_get(self):
        '''
        Setting an on_get so that the logging functionality can be used to queue multiple acquisitions.
        '''
        logger.info('requesting acquisition <{}>'.format(self._acquisition_count))
        if self.run_id is None:
            raise core.DriplineInternalError('run number is None, must request a run_id assignment prior to starting acquisition')
        filepath = '{directory}/{runN:09d}/{prefix}{runN:09d}_{acqN:09d}.egg'.format(
                                        directory=self.data_directory_path,
                                        prefix=self.filename_prefix,
                                        runN=self.run_id,
                                        acqN=self._acquisition_count
                                                  )
        request = core.RequestMessage(payload={'values':[], 'file':filepath},
                                      msgop=core.OP_RUN,
                                     )
        result = self.portal.send_request(self.mantis_queue,
                                          request=request,
                                         )
        if not result.retcode == 0:
            msg = ''
            if 'ret_msg' in result.payload:
                msg = result.payload['ret_msg']
            logger.warning('got an error from mantis: {}'.format(msg))
        else:
            self._acquisition_count += 1
            return "acquisition of [{}] requested".format(filepath)

    def end_run(self):
        self.logging_status = 'stop'
        super(MantisAcquisitionInterface, self).end_run()
        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(target=self.mantis_queue+'.stop-queue', request=request)
        if not result.retcode == 0:
            logger.warning('error stoping queue:\n{}'.format(result.return_msg))
        else:
            logger.warning('queue stopped')
        result = self.portal.send_request(target=self.mantis_queue+'.clear-queue', request=request)
        if not result.retcode == 0:
            logger.warning('error clearing queue:\n{}'.format(result.return_msg))
        else:
            logger.warning('queue cleared')
        result = self.portal.send_request(target=self.mantis_queue+'.start-queue', request=request)
        if not result.retcode == 0:
            logger.warning('error restarting queue:\n{}'.format(result.return_msg))
        else:
            logger.warning('queue started')
        self._acquisition_count = 0


__all__.append('RSAAcquisitionInterface')
class RSAAcquisitionInterface(DAQProvider, EthernetProvider):
    '''
    A DAQProvider for interacting with the RSA
    '''
    def __init__(self,
                 max_nb_files=10000,
                 **kwargs):
        DAQProvider.__init__(self, **kwargs)
        EthernetProvider.__init__(self, **kwargs)
        self.max_nb_files = max_nb_files

    def start_run(self, run_name):
        super(RSAAcquisitionInterface, self).start_run(run_name)
        # ensure the output format is set to mat
        self.send(["SENS:ACQ:FSAV:FORM MAT;*OPC?"])
        # build strings for output directory and file prefix, then set those
        file_directory = "\\".join([self.data_directory_path, '{:09d}'.format(self.run_id)])
        file_base = "{}{:09d}".format(self.filename_prefix, self.run_id)
        self.send(['SENS:ACQ:FSAV:LOC "{}"'.format(file_directory),
                   'SENS:ACQ:FSAV:NAME:BASE "{}"'.format(file_base),
                   "*OPC?"
                  ]
                 )
        # Set the maximum number of events (note that the default is 10k)
        self.send(['SENS:ACQ:FSAV:FILE:MAX {:d};*OPC?'.format(self.max_nb_files)])
        # try to force external reference
        ext_ref_error = self.send(['SENS:ROSC:SOUR EXT;*OPC?'])
        if int(ext_ref_error) == 2028:
            raise dripline.core.exceptions.DriplineHardwareConnectionError('External frequency reference signal is not valid.')
        elif int(ext_ref_error) == 2029:
            raise dripline.core.exceptions.DriplineHardwareConnectionError('Unable to lock to external frequency reference.')
        # ensure in triggered mode
        self.send(['TRIG:SEQ:STAT 1;*OPC?'])
        # actually start to FastSave
        self.send(['SENS:ACQ:FSAV:ENAB 1;*OPC?'])

    def end_run(self):
        # something to stop FastSave
        self.send(['SENS:ACQ:FSAV:ENAB 0'])
        self.send(['TRIG:SEQ:STAT 0;*OPC?'])
        super(RSAAcquisitionInterface, self).end_run()

    def determine_RF_ROI(self):
        logger.info('trying to determine roi')
        logger.warning('RSA does not support proper determination of RF ROI yet')