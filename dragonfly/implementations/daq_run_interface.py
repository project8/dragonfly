'''
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
		 Linux_not_Windows_DAQ = True,
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
	self.Linux_not_Windows_DAQ = Linux_not_Windows_DAQ

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
        '''

        self._run_name = run_name
	self._run_meta = {'DAQ': self.daq_name,
                          'run_time': self._run_time,
                         }

        self._do_prerun_gets()
        #self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')

    def end_run(self):
        '''
        Send command to the DAQ provider to stop data taking, do the post-run snapshot, and announce the end of the run.
        '''
        # call _stop_data_taking DAQ-specific method
        self._stop_data_taking()

        if self.run_id is None:
            raise core.DriplineValueError("No run to end: run_id is None.")
        self._do_snapshot()
        run_was = self.run_id
        self._run_name = None
        self.run_id = None
        logger.info('run <{}> ended'.format(run_was))

    def _do_prerun_gets(self):
        logger.info('doing prerun meta-data get')
        meta_result = self.provider.get(self._metadata_state_target, timeout=30)
        self._run_meta.update(meta_result['value_raw'])
        self.determine_RF_ROI()

    def _do_snapshot(self):
        logger.info('requesting snapshot of database')
        filename = '{directory}/{runN:09d}/{prefix}{runN:09d}_snapshot.json'.format(
                                                        directory=self.meta_data_directory_path,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id
                                                                               )
        time_now = datetime.utcnow().strftime(core.constants.TIME_FORMAT)
        snap_state = self.provider.cmd(self._snapshot_state_target,'take_snapshot',[self._start_time,time_now,filename],timeout=30)
        logger.info('snapshot returned ok')

    def determine_RF_ROI(self):
        raise core.exceptions.DriplineMethodNotSupportedError('subclass must implement RF ROI determination')

    def _send_metadata(self):
        '''
        '''
        logger.info('metadata should broadcast')
        logger.info(self.meta_data_directory_path)
	logger.info(self.filename_prefix)
	logger.info(self.run_id)
	logger.info(self._acquisition_count)
	filename = '{directory}/{runN:09d}/{prefix}{runN:09d}_meta.json'.format(
                                                        directory=self.meta_data_directory_path,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id
                                                                               )
        logger.debug('should request metadatafile: {}'.format(filename))
        this_payload = {'contents': self._run_meta,
                        'filename': filename,
                       }
        this_payload['contents']['run_id'] = self.run_id
        # note, the following line has an empty method/RKS, this shouldn't be the case but is what golang expects
        req_result = self.provider.cmd(self._metadata_target, None, payload=this_payload)
        logger.debug('meta sent')

    def start_timed_run(self, run_name, run_time):
        '''
        '''
        self._run_time = int(run_time)
        if self._daq_in_safe_mode:
            logger.info("DAQ in safe mode")
            raise core.exceptions.DriplineDAQNotEnabled("{} is not enabled: enable it using <dragonfly cmd broadcast.set_condition 0 -b myrna.p8>".format(self.daq_name))

        # self.start_run(run_name)
        logger.debug('testing if the DAQ is running')
        result = self.is_running
        if result == True:
            raise core.exceptions.DriplineDAQRunning('DAQ is already running: aborting run')

        # do the last minutes checks: DAQ specific
        self._do_checks()

        # get run_id and do pre_run gets
        self.start_run(run_name)

        # call start_run method in daq_target
	if self.Linux_not_Windows_DAQ!=True:
	    directory = os.path.join("\\",self.data_directory_path, '{:09d}'.format(self.run_id))
	else:
	    directory = os.path.join(self.data_directory_path, '{:09}'.format(self.run_id))

        filename = "{}{:09d}".format(self.filename_prefix, self.run_id)
        self._start_data_taking(directory,filename)
        return self.run_id

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

        # naming prefixes are not currently implemented, but maintained in code for consistency
        #self.instrument_setup_filename_prefix = instrument_setup_filename_prefix
        #self.mask_filename_prefix = mask_filename_prefix

    @property
    def is_running(self):
        result = self.provider.get("rsa_trigger_status")
        logger.info('RSA trigger status is <{}>'.format(result['value_cal']))
        return bool(int(result['value_raw']))

    def _do_checks(self):
        the_ref = self.provider.set('rsa_osc_source', 'EXT')['value_raw']
        if the_ref != 'EXT':
            raise core.exceptions.DriplineGenericDAQError('RSA external ref found to be <{}> (!="EXT")'.format(the_ref))

        # counting the number of errors in the RSA system queue and aborting the data taking if Nerrors>0
        Nerrors = self.provider.get('rsa_system_error_count')['value_raw']
        if Nerrors != '0':
            raise core.exceptions.DriplineGenericDAQError('RSA system has {} error(s) in the queue: check them with <dragonfly get rsa_system_error_queue -b myrna.p8>'.format(Nerrors))

        return "checks successful"

    def _start_data_taking(self,directory,filename):
        self.provider.cmd(self._daq_target, 'start_run', [directory, filename])
        logger.info("Adding {} sec timeout for run <{}> duration".format(self._run_time, self.run_id))
        self._stop_handle = self.service._connection.add_timeout(self._run_time, self.end_run)

    def _stop_data_taking(self):
        self.provider.cmd(self._daq_target, 'end_run')
        if self._stop_handle is not None:
            logger.info("Removing sec timeout for run <{}> duration".format(self.run_id))
            self.service._connection.remove_timeout(self._stop_handle)
            self._stop_handle = None

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



__all__.append('PsyllidAcquisitionInterface')
class PsyllidAcquisitionInterface(DAQProvider, core.Spime):
    '''
    A DAQProvider for interacting with Psyllid DAQ
    '''
    def __init__(self,
                 psyllid_queue='psyllid',
                 roach2_queue = 'roach2_interface',
                 #psyllid_preset = 'str-1ch',
                 #udp_receiver_port = 23530,
                 filename_prefix = 'psyllid',
                 hf_lo_freq = None,
                 **kwargs
                ):

        DAQProvider.__init__(self, **kwargs)

        self.psyllid_queue = psyllid_queue
        self.roach2_queue = roach2_queue
        self.filename_prefix = filename_prefix
        self._acquisition_count = 0
        self.run_id = 0

        self.status = None
        self.status_value = None
        self.duration = None
        self.central_frequency = None
        self.multi_channel_daq = False
        
        self.channel_dictionary = {'a': 0, 'b': 1, 'c': 2}
        self.freq_dict = {'a': None, 'b': None, 'c': None}
        
        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the psyllid acquisition interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq



    def _finish_configure(self):
        logger.debug('Configuring Psyllid')
        is_running = self._request_psyllid_status()
        if is_running:
            if self.status_value != 0:
                self.deactivate()
        else:
            raise core.DriplineInternalError('Cannot configure psyllid')
            
        if self.multi_channel_daq == True:
            self.freq_dict = self._get_roach_central_freqs()
            self._set_all_freqs()
	else:
	    self.activate()

    def _request_psyllid_status(self):
        logger.info('Checking Psyllid status')
        
        try:
            result = self.provider.get(self.psyllid_queue+'.daq-status', timeout=10)
            self.status = result['server']['status']
            self.status_value = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status))
            logger.info('Status in numbers: {}'.format(self.status_value))
            return True

        except:
            logger.warning('Psyllid is not running or sth. else is wrong')
            self.status=None
            self.status_value=None
            logger.info('Status is {}'.format(self.status))
            return False
        

    def is_running(self):
        self._request_psyllid_status()
        if self.status_value==5:
            return True
        else:
            return False
            

    def _check_roach2_status(self):

        #call is_running
        result = self.provider.cmd(self.roach2_queue, 'is_running')

        if result['values'][0]==False:
            logger.warning('The ROACH2 is not running!')
            return False

        elif result['values'][0]==True:

            #get calibration and configuration status
            result = self.provider.cmd(self.roach2_queue, 'get_calibration_status')
            self.roach2calibrated=result['values'][0]

            result = self.provider.cmd(self.roach2_queue, 'get_configuration_status')
            self.roach2configured=result['values'][0]

            #print results
            logger.info('Configured: {}, Calibrated: {}'.format(self.roach2configured, self.roach2calibrated))

            return True
        else:
            return False
            
            
    def _do_checks(self):
        #checking psyllid
        if self._request_psyllid_status()!=True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not responding')

        if self.status_value!=4:
            raise core.exceptions.DriplineGenericDAQError('Psyllid DAQ is not in activated status')

        #checking roach
        is_roach_running = self._check_roach2_status()
        
        if is_roach_running == False:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not responding')
            
        if self.roach2configured ==False:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 has not been programmed and configured by roach roach service')

        if self.roach2calibrated==False:
            logger.warning('The ADC was not calibrated. Data taking not recommended.')
        
        #check frequency matches
        if self.multi_channel_daq==True:
            roach_freqs = self._get_roach_central_freqs()
            for channel in roach_freqs.keys():
                if roach_freqs[channel]!=self.freq_dict[channel]:
                    raise core.exceptions.DriplineGenericDAQError('Frequency mismatch')
        
        return "checks successful"


    def determine_RF_ROI(self):
        logger.info('trying to determine roi')

        self._run_meta['RF_HF_MIXING'] = float(self._hf_lo_freq)
        logger.debug('RF High stage mixing: {}'.format(self._run_meta['RF_HF_MIXING']))

        logger.info('Getting central frequency from ROACH2')
        result = self.provider.cmd(self.roach2_queue, 'get_central_frequency')
        logger.info('Central frequency is: {}'.format(result['values'][0]))

        self._run_meta['RF_ROI_MIN'] = float(result['values'][0]-50e6) + float(self._hf_lo_freq)
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

        self._run_meta['RF_ROI_MAX'] = float(result['values'][0]+50e6) + float(self._hf_lo_freq)
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))



    def _start_data_taking(self, directory, filename):
        
        filename = filename+self._run_name+'.egg'
	logger.info(filename)
	logger.info(directory)
        if self._run_time>=5000:
            raise('With this duration the filesize is too big for testing')

        if not os.path.exists(directory):
            os.makedirs(directory)
        #self.set_path(filepath+filename)
        logger.info('Going to tell psyllid to start the run')
        payload = {'filename': os.path.join(directory, filename), 'duration':self._run_time}
        result = self.provider.cmd(self.psyllid_queue, 'start-run', payload=payload)


    def _set_condition(self, number):
        if number in self._set_condition_list:
            logger.debug('deactivating psyllid daq')
            self.deactivate()
        elif number == 0:
            logger.debug('getting out of safe mode')
        else:
            logger.debug('condition {} is unknown: ignoring!'.format(number))

# Other communication with psyllid and the roach        
            
        
    def _set_roach_central_freq(self, cf, channel):
        #no idea whether this works
        payload={'cf':cf, 'channel':channel}
        result = self.provider.cmd(self.roach2_queue, 'set_central_frequency', payload=payload)
        return result['values'][0]
 
 
    def _get_roach_central_freqs(self):
        result = self.provider.cmd(self.roach2_queue, 'get_all_central_frequencies')
        logger.info('central freq {}'.format(result))
        return result

    def _set_all_freqs(self):
        try:
            for channel in self.channel_dictionary.keys():
                cf_in_MHz = round(self.freq_dict[channel]*10**-6)
                request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.strw.center-freq'
                result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                logger.info('Set central frequency of streaming writer for channel {}'.format(channel))
        except:
            try:
                for channel in self.channel_dictionary.keys():
                    cf_in_MHz = round(self.freq_dict[channel]*10**-6)
                    request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.ew.center-freq'
                    result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                    logger.info('Set central frequency of egg writer for channel {}'.format(channel))
            except:
                logger.error('Could not set central frequency')
        return self.reactivate()
        
        
    def set_central_frequency(self, cf, channel='a'):
        cf = self._set_roach_central_freq(cf, channel)
        self.freq_dict[channel]=cf
        logger.info(cf)
        cf_in_MHz = round(cf*10**-6)
        logger.info('cf in MHz: {}'.format(cf_in_MHz))
        try:
             request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.strw.center-freq'
             result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
             logger.info('Set central frequency of streaming writer')
        except:
            try:
                request = '.node-config.ch'+str(self.channel_dictionary[channel])+'.ew.center-freq'
                result = self.provider.set(self.psyllid_queue+request, cf_in_MHz)
                logger.info('Set central frequency of egg writer')
            except:
                logger.error('Could not set central frequency')

        return self.reactivate()
	

#    def set_path(self, filepath):
#        result = self.provider.set(self.psyllid_queue+'.filename', filepath)
        #self.get_path()

    def start_multi_channel_daq(self):
        self.multi_channel_daq = True
        self._finish_configure()
        
    def auto_channel_config(self):
        logger.warning('Not implemented yet')
        return False

    def get_path(self):
        result = self.provider.get(self.psyllid_queue+'.filename')
        logger.info('Egg filename is {} path is {}'.format(result['values'], self.data_directory_path))
        return result['values']

    def change_data_directory_path(self,path):
        self.data_directory_path = path
        return self.data_directory_path


#    def set_duration(self, duration):
#        result = self.provider.set(self.psyllid_queue+'.duration', duration)
#	self.duration = duration



    def activate(self):
        if self.status_value == 6:
            self.is_running()
        elif self.status_value == 0:
            logger.info('Activating Psyllid')
            result = self.provider.cmd(self.psyllid_queue, 'activate-daq')
            self._request_psyllid_status()
            return True

        else:
            logger.warning('Could not activate Psyllid')
            return False


    def deactivate(self):
        if self.status != 0:
            logger.info('Deactivating Psyllid')
            result = self.provider.cmd(self.psyllid_queue,'deactivate-daq')
            self._request_psyllid_status()
        if self.status_value!=0:
            logger.warning('Could not deactivate Psyllid')
            return False
        else: return True

    def reactivate(self):
        if self.status_value != 0:
            logger.info('Reactivating Psyllid')
            result = self.provider.cmd(self.psyllid_queue, 'reactivate-daq')
            self._request_psyllid_status()
	    return True
	elif self.status_value==0:
	    self.activate()
	else:
	    logger.warning('Could not reactivate Psyllid')
    	    return False


    def quit_psyllid(self):
        result = self.provider.cmd(self.psyllid_queue, 'quit-psyllid')
        logger.info('psyllid quit')

