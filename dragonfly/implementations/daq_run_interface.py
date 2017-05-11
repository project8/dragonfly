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
                 #Linux_not_Windows_DAQ = True,
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
        #self.Linux_not_Windows_DAQ = Linux_not_Windows_DAQ

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

        if self.run_id is None:
            raise core.exceptions.DriplineValueError("No run to end: run_id is None.")
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
        directory = '{base}/{runNyx:03d}yyyxxx/{runNx:06d}xxx/{runN:09d}'.format(
                                                                    base=self.data_directory_path,
                                                                    runNyx=self.run_id/1000000,
                                                                    runNx=self.run_id/1000,
                                                                    runN=self.run_id
                                                                   )
	#if self.Linux_not_Windows_DAQ!=True:
        #    directory = os.path.join("\\",self.data_directory_path, '{:09d}'.format(self.run_id))
        #else:
        #    directory = os.path.join(self.data_directory_path, '{:09}'.format(self.run_id))

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



__all__.append('ROACH1ChAcquisitionInterface')
class ROACH1ChAcquisitionInterface(DAQProvider):
    '''
    A DAQProvider for interacting with ROACH-Psyllid DAQ
    '''
    def __init__(self,
                 psyllid_interface='psyllid_interface',
                 daq_target = 'roach2_interface',
                 channel = 'a',
                 filename_prefix = 'psyllid',
                 hf_lo_freq = None,
                 **kwargs
                ):

        DAQProvider.__init__(self, **kwargs)

        self.psyllid_interface = psyllid_interface
        self.daq_target = daq_target
        self.filename_prefix = filename_prefix
        self.status_value = None
        self.channel_id = channel
        self.freq_dict = {self.channel_id: None}
        self._max_duration = 1
        self._run_time = 1
        self._run_name = "test"


        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the Psyllid acquisition interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq



    def _finish_configure(self):
        logger.info('Doing setup checks...')
        self._check_psyllid_instance()
        
        if self.status_value == 0:
            result = self.provider.cmd(self.psyllid_interface, 'activate', payload = self.payload_channel)
            self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)['values'][0]
                
        if self._check_roach2_status()==True:
            logger.info('Setting Psyllid central frequency identical to ROACH2 central frequency')
            freqs = self._get_roach_central_freqs()
            self.central_frequency = freqs[self.channel_id]
            return True

    @property
    def is_running(self):
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)
        if self.status_value==5:
            return True
        else:
            return False


    def set_max_duration(self, duration):
        self._max_duration = duration
        return self._max_duration


    def _check_roach2_status(self):
        logger.info('Checking ROACH2 status')
        #call is_running from roach2_interface
        try: 
            result = self.provider.cmd(self.daq_target, 'is_running')
        except:
            logger.error('Failed to request ROACH2 status')
            raise core.exceptions.DriplineGenericDAQError('Cannot request roach status from {}'.format(self.daq_target))

        if result['values'][0]==False:
            logger.error('ROACH2 status request returned False')
            raise core.exceptions.DriplineGenericDAQError('ROACH2 not ready for data taking')
        elif result['values'][0]==True:
            logger.info('ROACH2 is ready')
            return True
        else:
            return False


    def _check_psyllid_instance(self):
        logger.info('Checking Psyllid service & instance')

        #check psyllid is responding by requesting status
        self.payload_channel = {'channel':self.channel_id}
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status', payload = self.payload_channel)['values'][0]
        if self.status_value == None:
            logger.error('Psyllid is not responding')
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not responding')        

        #check channel match
        Nstreams = self.provider.cmd(self.psyllid_interface, 'get_number_of_streams', payload = self.payload_channel)['values'][0]
        if Nstreams != 1:
            logger.error('Wrong number of Psyllid channels are active under this queue')
            raise core.exceptions.DriplineValueError('Wrong number of Psyllid channels are active under this queue')

        active_channels = self.provider.cmd(self.psyllid_interface, 'get_active_channels')['values'][0]
        if self.channel_id in active_channels==False:
            logger.error('The Psyllid and ROACH2 channel interfaces do not match')
            raise core.exceptions.DriplineGenericDAQError('The Psyllid and ROACH channel interfaces do not match')


    def _do_checks(self):
        if self._run_time ==0:
            raise core.exceptions.DriplineValueError('run time is zero')
        #elif self._run_time >= self._max_duration:
        #    raise core.exceptions.DriplineValueError('run time exceeds max duration')

        #checking psyllid
        if self.is_running==True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is already running')

        self._check_psyllid_instance()

        if self.status_value!=4:
            raise core.exceptions.DriplineGenericDAQError('Psyllid DAQ is not activated')

        #checking roach
        if self._check_roach2_status() == False:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not ready')

        #check frequency matches
        roach_freqs = self._get_roach_central_freqs()
        psyllid_freqs = self._get_psyllid_central_freqs()
        if roach_freqs[self.channel_id]!=psyllid_freqs[self.channel_id]:
            raise core.exceptions.DriplineGenericDAQError('Frequency mismatch')

        return "checks successful"


    def determine_RF_ROI(self):
        logger.info('trying to determine roi')

        self._run_meta['RF_HF_MIXING'] = float(self._hf_lo_freq)
        logger.debug('RF High stage mixing: {}'.format(self._run_meta['RF_HF_MIXING']))

        logger.info('Getting central frequency from ROACH2')
        cfs = self._get_roach_central_freqs()
        cf = cfs[self.channel_id]
        logger.info('Central frequency is: {}'.format(cf))

        self._run_meta['RF_ROI_MIN'] = float(cf-50e6) + float(self._hf_lo_freq)
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

        self._run_meta['RF_ROI_MAX'] = float(cf+50e6) + float(self._hf_lo_freq)
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))



    def _start_data_taking(self, directory, filename):
        logger.info('block roach channel')
        result = self.provider.cmd(self.daq_target, 'block_channel', payload=self.payload_channel)
        logger.info('start data taking')

        try:
            # switching from seconds to milisecons
            duration = self._run_time*1000.0
            max_duration = self._max_duration*1000.0
            logger.info('run duration in ms: {}'.format(duration))

            NAcquisitions = duration/max_duration

            if NAcquisitions<=1:
                psyllid_filename = filename+'.egg'

                if not os.path.exists(directory):
                    os.makedirs(directory)

                logger.info('Going to tell psyllid to start the run')
                payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':duration}
                result = self.provider.cmd(self.psyllid_interface, 'start_run', payload=payload)

            # if the run time exceeds the set max duration the run is split into sub acquisitions
            else:
                logger.info('Doing {} acquisitions'.format(int(NAcquisitions)))

                for i in range(int(NAcquisitions)):
                    total_run_time = 0.0
                    psyllid_filename = filename+'_'+str(i)+'.egg'
                    logger.info('Data will be written to {}/{}'.format(directory, psyllid_filename))
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                    # last acquisition
                    if total_run_time > duration-max_duration:
                        duration = duration-total_run_time
                        logger.info('Going to tell psyllid to start the last run')
                        payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':duration}
                        result = self.provider.cmd(self.psyllid_interface, 'start_run', payload=payload)
                    # acquisitions with duration = max_duration
                    else:
                        total_run_time+=max_duration
                        logger.info('Going to tell psyllid to start run')
                        payload = {'channel':self.channel_id, 'filename': os.path.join(directory, psyllid_filename), 'duration':max_duration}
                        result = self.provider.cmd(self.psyllid_interface, 'start_run', payload=payload)
                    time.sleep(self._max_duration)
        except:
            logger.error('Starting Psyllid run failed')

        logger.info('unblock channel')
        payload = {'channel': self.channel_id}
        result = self.provider.cmd(self.daq_target, 'unblock_channel', payload=payload)


    def stop_psyllid(self):
        # in case things go really wrong...
        result = self.provider.cmd(self.psyllid_interface, 'quit_psyllid', payload = self.payload_channel)
        result = self.provider.cmd(self.daq_target, 'unblock_channel', payload=self.payload_channel)

#    def _set_condition(self, number):
#        if number in self._set_condition_list:
#            logger.debug('deactivate psyllid daq')
#            result = self.provider.cmd(self.psyllid_interface, 'activate', payload = self.payload_channel)
#        elif number == 0:
#            logger.debug('getting out of safe mode')
#        else:
#            logger.debug('condition {} is unknown: ignoring!'.format(number))


# frequency settings and gettings

    def _get_roach_central_freqs(self):
        result = self.provider.cmd(self.daq_target, 'get_all_central_frequencies')
        logger.info('ROACH central freqs {}'.format(result))
        return result


    def _get_psyllid_central_freqs(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_all_central_frequencies')
        logger.info('Psyllid central freqs {}'.format(result))
        return result


    @property
    def central_frequency(self):
        return self.freq_dict[self.channel_id]


    @central_frequency.setter
    def central_frequency(self, cf):
        payload={'cf':cf, 'channel':self.channel_id}
        result = self.provider.cmd(self.daq_target, 'set_central_frequency', payload=payload)
        # The roach frequency can differ from the requested frequency. Psyllid should have the same frequency settings as the ROACH
        self.freq_dict[self.channel_id]=result['values'][0]
        payload={'channel':self.channel_id, 'cf':self.freq_dict[self.channel_id], 'channel':self.channel_id}
        result = self.provider.cmd(self.psyllid_interface, 'set_central_frequency', payload=payload)
        if result['values'][0]!=True:
            logger.warning('Could not set central frequency in Psyllid')


    def make_trigger_mask(self, snr = 11, filename = '/home/roach/trigger_masks/psyllid_trigger_mask'):
        # Set threshold snr
        payload = {'channel':self.channel_id, 'snr':snr}
        result = self.provider.cmd(self.psyllid_interface, 'set_fmt_snr_threshold', payload = payload)
        time.sleep(1)
        # Acquire and save new mask
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = filename+'_channel_'+self.channel_id+'_'+timestr+'.json'
        payload = {'channel':self.channel_id, 'filename':filename}
        result = self.provider.cmd(self.psyllid_interface, 'make_trigger_mask', payload=payload)
        if result['values'][0]!=True:
            return False
        else: return True




__all__.append('ROACHMultiChAcquisitionInterface')
class ROACHMultiChAcquisitionInterface(DAQProvider, core.Spime):
    '''
    A DAQProvider for interacting with ROACH-Psyllid DAQ
    '''
    def __init__(self,
                 psyllid_interface='psyllid_interface',
                 daq_target = 'roach2_interface',
                 number_of_channels = 3,
                 channel_id_1 = 'a',
                 channel_id_2 = 'b',
                 channel_id_3 = 'c',
                 mode = 'identical_cf', #other modes: window_overlap, independent
                 filename_prefix = 'psyllid',
                 ROI_overlap = 10.0e6,
                 hf_lo_freq = None,
                 **kwargs
                ):

        DAQProvider.__init__(self, **kwargs)

        self.psyllid_interface = psyllid_interface
        self.daq_target = daq_target
        self.filename_prefix = filename_prefix
        self.run_id = 0

        self.status_value = None
        self._max_duration = 1000000
        self.ROI_overlap = ROI_overlap

        self.mode = mode
        self.number_of_channels = number_of_channels
        if self.number_of_channels ==2:
            self.channel_ids = [channel_id_1, channel_id_2]
            self.freq_dict = {self.channel_ids[0]: None, self.channel_ids[1]: None}
        elif self.number_of_channels ==3:
            self.channel_ids = [channel_id_1, channel_id_2, channel_id_3]
            self.freq_dict = {self.channel_ids[0]: None, self.channel_ids[1]: None, self.channel_ids[2]: None}
        else:
            raise core.exceptions.DriplineValueError('No valid channel number')

        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the psyllid acquisition interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq


    def _finish_configure(self):
        logger.info('Doing setup checks')

        self._check_psyllid_instance()
        if self.status_value == 0:
            result = self.provider.cmd(self.psyllid_interface, 'activate')
            self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status')['values'][0]

        self._check_roach2_status()

        logger.info('Setting default central frequency')
        if self.mode=='independent':
            for i in self.channel_ids:
                self._set_central_frequency(800e6, i)
        else:
            self.set_central_frequency(800e6)


    def get_number_of_channels(self):
        return self.number_of_channels

    def get_frequency_overlap(self):
        return self.ROI_overlap

    def set_frequency_overlap(self, overlap):
        self.ROI_overlap = overlap

    def get_mode(self):
        return self.mode

    def set_mode(self, mode):
        if mode == 'identical_cf':
            self.mode = mode
        elif mode == 'window_overlap':
            self.mode = mode
        elif mode == 'independent':
            self.mode = mode
        else:
            logger.info('{} is not a valid mode name'.format(mode))
            return False
        self._finish_configure()


    def is_running(self):
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status')['values'][0]
        if self.status_value==5:
            return True
        else:
            return False


    def _check_roach2_status(self):
        logger.info('Checking ROACH2 status')

        #call is_running
        result = self.provider.cmd(self.daq_target, 'is_running')
        if result['values'][0]==False:
            logger.warning('The ROACH2 is not running!')
            raise core.exceptions.DriplineGenericDAQError('The ROACH2 is not ready for data taking')
        elif result['values'][0]==True:
            return True
        else:
            logger.warning('Undefined ROACH2 status')
            return False


    def _check_psyllid_instance(self):
        logger.info('Checking Psyllid service & instance')

        #check psyllid is responding by requesting status
        self.status_value = self.provider.cmd(self.psyllid_interface, 'request_status')['values'][0]
        if self.status_value == None:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is not responding')
       
        #check channel match
        Nstreams = self.provider.cmd(self.psyllid_interface, 'get_number_of_streams')['values'][0]
        if Nstreams != self.number_of_channels:
            raise core.exceptions.DriplineValueError('Wrong number of Psyllid channels are active under this queue')

        active_channels = self.provider.cmd(self.psyllid_interface, 'get_active_streams')['values'][0]
        for i in self.channel_ids:
            if i in active_channels==False:
                raise core.exceptions.DriplineGenericDAQError('The Psyllid and ROACH channel interfaces do not match')


    def _do_checks(self):
        #check psyllid

        if self.is_running()==True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid is already running')

        self._check_psyllid_instance()
        if self.status_value!=4:
            raise core.exceptions.DriplineGenericDAQError('Psyllid DAQ is not in activated status')

        #check roach
        is_roach_running = self._check_roach2_status()

        if is_roach_running == False:
            raise core.exceptions.DriplineGenericDAQError('ROACH2 is not ready for data taking')

        #check frequency matches
        roach_freqs = self._get_roach_central_freqs()
        psyllid_freqs = self._get_psyllid_central_freqs()
        for i in self.channel_ids:
            if int(roach_freqs[i]*10**-6)!=int(psyllid_freqs[i]*10**-6):
                logger.warning('Channel {}, ROACH cf is {} MHz, Psyllid stream cf is {} MHz'.format(i, int(roach_freqs[i]*10**-6), int(psyllid_freqs[i]*10**-6)))
                raise core.exceptions.DriplineGenericDAQError('Frequency mismatch')

        return "checks successful"


    def determine_RF_ROI(self):
        logger.info('Determining RF FOI')
        if self.mode=='independent':
            raise core.exceptions.DriplineGenericDAQError('No RF ROI for independent mode defined')

        elif self.mode=='identical_cf':
            logger.info('trying to determine roi')

            self._run_meta['RF_HF_MIXING'] = float(self._hf_lo_freq)
            logger.debug('RF High stage mixing: {}'.format(self._run_meta['RF_HF_MIXING']))

            result = self.provider.cmd(self.daq_target, 'get_central_frequency')
            logger.info('Central frequency is: {}'.format(self.central_frequency))

            self._run_meta['RF_ROI_MIN'] = float(self.central_frequency-50e6) + float(self._hf_lo_freq)
            logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

            self._run_meta['RF_ROI_MAX'] = float(self.central_frequency+50e6) + float(self._hf_lo_freq)
            logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))


        elif self.mode=='window_overlap':
            logger.info('trying to determine roi')

            self._run_meta['RF_HF_MIXING'] = float(self._hf_lo_freq)
            logger.debug('RF High stage mixing: {}'.format(self._run_meta['RF_HF_MIXING']))

            result = self.provider.cmd(self.daq_target, 'get_central_frequency')
            logger.info('Central frequency is: {}'.format(self.central_frequency))

            if self.number_of_channels == 2:
                self._run_meta['RF_ROI_MIN'] = float(self.freq_dict[self.channel_ids[0]]-50e6) + float(self._hf_lo_freq)
                logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

                self._run_meta['RF_ROI_MAX'] = float(self.freq_dict[self.channel_ids_[1]]+50e6) + float(self._hf_lo_freq)
                logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))

            elif self.number_of_channels == 3:
                self._run_meta['RF_ROI_MIN'] = float(self.freq_dict[self.channel_ids[0]]-50e6) + float(self._hf_lo_freq)
                logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))

                self._run_meta['RF_ROI_MAX'] = float(self.freq_dict[self.channel_ids[2]]+50e6) + float(self._hf_lo_freq)
                logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))
            else:
                raise core.exceptions.DriplineGenericDAQError('Number of channels')
        else:
            raise core.exceptions.DriplineGenericDAQError('Sth went wrong')



    def _start_data_taking(self, directory, filename):
        logger.info('block roach channels')
        for i in self.channel_ids:
            payload = {'channel':i}
            result = self.provider.cmd(self.daq_target, 'block_channel', payload = payload)
        try:
            duration = self._run_time*1000
            psyllid_filename = filename+'_'+self._run_name+'.egg'

            if self._run_time>=5000:
                raise('With this duration the filesize is too big for testing')

            if not os.path.exists(directory):
                os.makedirs(directory)

            logger.info('Going to tell Psyllid to start the run')
            payload = {'filename': os.path.join(directory, psyllid_filename), 'duration':duration}
            result = self.provider.cmd(self.psyllid_interface, 'start-run', payload=payload)
        except:
            logger.error('Starting Psyllid run failed')
            
        logger.info('unblock roach channels')
        for i in self.channel_ids:
            payload = {'channel':i}
            result = self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)


    def emergeny_stop(self):
        result = self.provider.cmd(self.psyllid_interface, 'quit_psyllid')
        for i in self.channel_ids.keys():
            payload = {'channel':i}
            result = self.provider.cmd(self.daq_target, 'unblock_channel', payload = payload)
        return True

#    def _set_condition(self, number):
#        if number in self._set_condition_list:
#            logger.debug('deactivating psyllid daq')
#            self.deactivate()
#        elif number == 0:
#            logger.debug('getting out of safe mode')
#        else:
#            logger.debug('condition {} is unknown: ignoring!'.format(number))


# Other communication with psyllid and the roach

    def set_central_frequencies(self, cf1, cf2, cf3):
        if self.mode=='idenpendent':
            logger.info('This is 2 Channel ROACH DAQ speaking: setting identical cf to both channels')
            self._set_central_frequency(cf1, self.channel_ids[0])
            self._set_central_frequency(cf1, self.channel_ids[1])
            self._set_central_frequency(cf3, self.channel_ids[2])
            return self.freq_dict
        else:
            logger.error('Use set_central_frequency in this mode')
            return False


    def _set_central_frequency(self, cf, channel):
        logger.info('Setting central frequency of channel {} to {} Hz'.format(channel, cf))
        payload={'cf':cf, 'channel': channel}
        result = self.provider.cmd(self.daq_target, 'set_central_frequency', payload=payload)
        self.freq_dict[channel] = result['values'][0]
        payload={'cf':self.freq_dict[channel], 'channel':channel}
        result = self.provider.cmd(self.psyllid_interface, 'set_central_frequency', payload=payload)
        logger.info(result['values'][0])
        if result['values'][0] != True:
            raise core.exceptions.DriplineGenericDAQError('Psyllid interface could not set central frequency')


    def set_central_frequency(self, cf):
        if self.mode=='identical_cf':
            self.central_frequency = cf
            logger.info('Multi channel roach daq in "identical_cf" mode. Setting identical cf for all channels...')
            
            for i in self.channel_ids:
                self._set_central_frequency(cf, i)
            return self.freq_dict

        elif self.mode=='window_overlap':
            self.central_frequency = cf
            logger.info('Multi channel roach daq in "window_overlap" mode. Setting cf to {} Hz'.format(cf))

            if self.number_of_channels == 2:
                self._set_central_frequency(cf-50e6+self.ROI_overlap/2, self.channel_ids[0])
                self._set_central_frequency(cf+50e6-self.ROI_overlap/2, self.channel_ids[1])
            elif self.number_of_channels == 3:
                self._set_central_frequency(cf-100e6+self.ROI_overlap, self.channel_ids[0])
                self._set_central_frequency(cf, self.channel_ids[1])
                self._set_central_frequency(cf+100e6-self.ROI_overlap, self.channel_ids[2])
            return self.freq_dict

        else:
            logger.error('Use "set_central_frequencies" in this mode')
            return False


    def get_central_frequencies(self):
        return self.freq_dict


    def _get_roach_central_freqs(self):
        result = self.provider.cmd(self.daq_target, 'get_all_central_frequencies')
        logger.info('central freq {}'.format(result))
        return result


    def _get_psyllid_central_freqs(self):
        result = self.provider.cmd(self.psyllid_interface, 'get_all_central_frequencies')
        logger.info('central freq {}'.format(result))
        return result

    def get_frequency_range(self):
        if self.mode == 'independent':
            return False
        elif self.mode == 'identical_cf':
            return [self.central_frequency-50e6, self.central_frequency+50e6]
        elif self.mode == 'window_overlap':
            return [self.freq_dict[self.channel_ids[0]]-50e6, self.freq_dict[self.channel_ids[2]]+50e6]
        else: return False

