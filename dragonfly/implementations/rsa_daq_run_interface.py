'''
A service for uniform interfacing with the RSA
'''

from __future__ import absolute_import


# standard imports
import logging
import json
from datetime import datetime

# internal imports
from dripline import core
from dragonfly.implementations import DAQProvider

__all__ = []

logger = logging.getLogger(__name__)

__all__.append('RSAAcquisitionInterface')

@core.fancy_doc
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
                 **kwargs):
        '''
        daq_target (str): name of DAQ provider in service to interface with 
        hf_lo_freq (int): hf local oscillator frequency in Hz
        instrument_setup_filename_prefix (str): prefix for instrument setup file, not currently implemented
        mask_filename_prefix (str): prefix for mask file name, not currently implemented
        trace_path (str): path to where to save the trace dpt file (currently, a drive on claude mounted on the RSA via samba)
        trace_metadata_path (str): path to where to save the metadata file (currently, a drive on claude)
        metadata_endpoints (list): list of metadata endpoint names (str) whose properties we save  
        '''
        DAQProvider.__init__(self, **kwargs)

        if daq_target is None:
            raise core.exceptions.DriplineValueError('the rsa acquisition interface requires a valid "daq_target" in its config file')
        self._daq_target = daq_target
        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the rsa acquisition interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq

        if isinstance(trace_path,str):
            self.trace_path = trace_path
            if not self.trace_path.endswith('/'):
                self.trace_path = trace_path + '/'
        else:
            logger.info("No trace_path given in the config file: save_trace feature disabled")
            self.trace_path = None
        if isinstance(trace_metadata_path,str):
            self.trace_metadata_path = trace_metadata_path
            if not trace_metadata_path.endswith('/'):
                self.trace_metadata_path = trace_metadata_path + '/'
        else:
            self.trace_metadata_path = None
        self._metadata_endpoints = metadata_endpoints

        # naming prefixes are not currently implemented, but maintained in code for consistency
        #self.instrument_setup_filename_prefix = instrument_setup_filename_prefix
        #self.mask_filename_prefix = mask_filename_prefix

    @property
    def is_running(self):
        '''
        Returns RSA trigger status as boolean
        '''
        result = self.provider.get("rsa_trigger_status")
        logger.info('RSA trigger status is <{}>'.format(result['value_cal']))
        return bool(int(result['value_raw']))

    def _do_checks(self):
        '''
        Sets RSA exeternal reference to EXT and checks for errors in queue which, if present, aborts the run 
        '''
        the_ref = self.provider.set('rsa_osc_source', 'EXT')['value_raw']
        if the_ref != 'EXT':
            raise core.exceptions.DriplineGenericDAQError('RSA external ref found to be <{}> (!="EXT")'.format(the_ref))

        # counting the number of errors in the RSA system queue and aborting the data taking if Nerrors>0
        Nerrors = self.provider.get('rsa_system_error_count')['value_raw']
        if Nerrors != '0':
            raise core.exceptions.DriplineGenericDAQError('RSA system has {} error(s) in the queue: check them with <dragonfly get rsa_system_error_queue -b myrna.p8>'.format(Nerrors))

        return "checks successful"

    def _start_data_taking(self,directory,filename):
        '''
        Sends stat run command to DAQ target
        '''
        self.provider.cmd(self._daq_target, 'start_run', [directory, filename])

    def _stop_data_taking(self):
        '''
        Sends end run command to DAQ target
        '''
        self.provider.cmd(self._daq_target, 'end_run')
        if self._stop_handle is not None:
            logger.info("Removing sec timeout for run <{}> duration".format(self.run_id))
            self.service._connection.remove_timeout(self._stop_handle)
            self._stop_handle = None

    def determine_RF_ROI(self):
        '''
        Gets RF roi information from provider and saves it as run metadata 
        '''
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
        '''
        Saves trace of RSA 
        '''
        if self.trace_path is None:
            raise DriplineValueError("No trace_path in RSA config file: save_trace feature disabled!")

        if isinstance(comment,(str,unicode)):
            comment = comment.replace(" ","_")
        datenow = datetime.now()
        filename = "{0:%Y}/{0:%m%d}/{0:%Y%m%d_%H%M%S}/{0:%Y%m%d_%H%M%S}_Trace{1}_{2}".format(datenow,trace,comment)

        logger.debug('saving trace')
        path = self.trace_path + filename
        self.provider.cmd('rsa_interface','_save_trace',[trace,path])
        logger.info("saving {}: successful".format(path))

        if self.trace_metadata_path is None:
            raise core.exceptions.DriplineValueError("No trace_metadata_path in RSA config file: metadata save disabled!")
        result_meta = {}
        if isinstance(self._metadata_endpoints,list):
            for endpoint_name in self._metadata_endpoints:
                result_meta.update(self.provider.get(endpoint_name,timeout=100)['value_raw'])
                logger.debug("getting {} endpoint: successful".format(endpoint_name))
        elif isinstance(self._metadata_endpoints,str):
            result_meta.update(self.provider.get(self._metadata_endpoints,timeout=100)['value_raw'])
            logger.debug("getting {} endpoint: successful".format(self._metadata_endpoints))
        else:
            raise core.exceptions.DriplineValueError("No valid metadata_endpoints in RSA config.")

        path = self.trace_metadata_path + "{}_metadata.json".format(filename)
        logger.debug("opening file")
        with open(path, "w") as outfile:
            logger.debug("things are about to be dumped in file")
            json.dump(result_meta, outfile, indent=4)
            logger.debug("things have been dumped in file")
            logger.info("saving {}: successful".format(path))

