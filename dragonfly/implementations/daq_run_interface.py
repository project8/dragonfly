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
                 filename_prefix='',
                 snapshot_state_target='',
                 metadata_state_target='',
                 metadata_target='',
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
        self._acquisition_count = None
        self._start_time = None
        self._run_meta = None
        self._run_snapshot = None
        self._run_time = None

        print('no errors from DAQ Provider')

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
        self._do_snapshot()
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

        self._run_name = run_name
	self._run_meta = {'DAQ': self.daq_name,
                          'run_time': self._run_time,
                         }

        self._do_prerun_gets()
        #self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')

    def _do_prerun_gets(self):
        logger.info('doing prerun meta-data get')
        meta_result = self.provider.get(self._metadata_state_target, timeout=30)
        self._run_meta.update(meta_result['value_raw'])
#        self.determine_RF_ROI()

    def _do_snapshot(self):
        logger.info('requesting snapshot of database')
        filename = '{directory}/{runN:09d}/{prefix}{runN:09d}_snapshot.json'.format(
                                                        directory=self.meta_data_directory_path,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id,
                                                        acqN=self._acquisition_count
                                                                               )
        time_now = datetime.utcnow().strftime(core.constants.TIME_FORMAT)
        snap_state = self.provider.cmd(self._snapshot_state_target,'take_snapshot',[self._start_time,time_now,filename],timeout=30)
        logger.info('snapshot returned ok')
#>>>>>>> develop

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
                                                        runN=self.run_id,
                                                        acqN=self._acquisition_count)
        logger.info(filename)
	logger.info(self._metadata_target)                                                         
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

    def start_run(self, run_name):
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
        #core.Spime.__init__(self, **kwargs)
        #self.alert_routing_key = 'daq_requests'

        self.psyllid_queue = psyllid_queue
        self.roach2_queue = roach2_queue
	self.filename_prefix = filename_prefix
        #self.timeout = timeout
	self._acquisition_count = 0
	self.run_id = 0

        self.status = None
        self.status_value = None
	self.duration = None
        #self.psyllid_preset = psyllid_preset
        #self.udp_receiver_port = udp_receiver_port
        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the psyllid acquisition interface requires a "hf_lo_freq" in its config file')
	self._hf_lo_freq = hf_lo_freq



    def _finish_configure(self):
        logger.debug('Configuring Psyllid')
        is_running = self.is_running()
        if is_running:
            if self.status_value == 4:
                self.deactivate()

            elif self.status_value!=0:
                raise core.DriplineInternalError('Status of Psyllid must be "Initialized", status is {}'.format(self.status))

            ##set daq presets
            #self.configure(self.psyllid_preset)

            ##set udp receiver port
            #self.set_udp_port(self.udp_receiver_port)

            #activate
            self.activate()
            return True

        else:
            logger.error('Psyllid could not be configured.')
            return False



    def is_running(self):
        logger.info('Checking Psyllid status')
        
        try:
            #result = self.portal.send_request(request=query_msg, target=self.psyllid_queue+'.daq-status', timeout=self.timeout)
            result = self.provider.get(self.psyllid_queue+'.daq-status', timeout=10)
            self.status = result['server']['status']
            self.status_value = result['server']['status-value']
            logger.info('Psyllid is running. Status is {}'.format(self.status))
            return True

        except:
            logger.warning('Psyllid is not running or sth. else is wrong')
            self.status=None
            self.status_value=None
            logger.info('Status is {}'.format(self.status))
            return False



    # set and get

    def set_udp_port(self, new_port):
        self.udp_receiver_port = new_port
        logger.info('Setting udp receiver port to {}'.format(self.udp_receiver_port))
        result = self.provider.set(self.psyllid_queue+'.node.udpr.port', self.udp_receiver_port)

    def get_udp_port(self):
        result = self.provider.get(self.psyllid_queue+'.node.udpr.port')
        logger.info('udp receiver port is: {}'.format(result.payload))
        return self.udp_receiver_port

    def set_path(self, filepath):
        result = self.provider.set(self.psyllid_queue+'.filename', filepath)
        #self.get_path()

    def get_path(self):
        result = self.provider.get(self.psyllid_queue+'.filename')
        logger.info('Egg filename is {} path is {}'.format(result['values'], self.data_directory_path))
        return result['values']

    def change_data_directory_path(self,path):
        self.data_directory_path = path
        return self.data_directory_path

    def set_description(self, description):
        result = self.provider.set(self.psyllid_queue+'.description', description)
        logger.info('Description set to:'.format(description))


    def set_duration(self, duration):
        result = self.provider.set(self.psyllid_queue+'.duration', duration)
	self.duration = duration

    def get_duration(self):
        result = self.provider.get(self.psyllid_queue+'.duration')
        logger.info('Duration is {}'.format(result.payload))
        return result.payload['values'][0]


    #other methods

    #def configure(self,config=None):
    #    if config == None:
    #        config = self.psyllid_preset
    #    logger.info('Configuring Psyllid with {}'.format(config))
    #    result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[config]}), target=self.psyllid_queue+'.daq-preset')

    #    if result.retcode >= 100:
    #        logger.warning('retcode indicates an error')
	#    return False
	#else:
	#    return True

    def activate(self):
        if self.status_value == 6:
            self.is_running()
        elif self.status_value == 0:
            logger.info('Activating Psyllid')
            request = core.RequestMessage(msgop=core.OP_CMD)
            result = self.provider.cmd(self.psyllid_queue, 'activate-daq')
            time.sleep(1)
            self.is_running()
            return True

        else:
            logger.warning('Could not activate Psyllid')
            return False


    def deactivate(self):
        if self.status != 0:
            logger.info('Deactivating Psyllid')
            result = self.provider.cmd(self.psyllid_queue,'deactivate-daq')
            time.sleep(1)
            self.is_running()
	if self.status!=0:
	    logger.warning('Could not deactivate Psyllid')
            return False
	else: return True



    def check_roach2_status(self):

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



    def start_timed_run(self, run_name, run_time, description=None):
        '''
        '''
        #checking psyllid
        if self.is_running()!=True:
            logger.error('Cannot start run. Psyllid is not running')
	    return False
	elif self.status!='Idle':
	    logger.error('Cannot start run. Psyllid status is not Idle')
	    return False

        #checking roach
        is_roach_running = self.check_roach2_status()
        if is_roach_running == False:
            return False

        elif is_roach_running == True:
            if self.roach2configured ==False:
                logger.warning('The ROACH2 might not be configured correctly. Check Roach2 service')
            if self.roach2calibrated==False:
                logger.warning('The adc is not calibrated. Data taking not recommended.')

        logger.info('runname is {}'.format(run_name))
        super(PsyllidAcquisitionInterface, self).start_run(run_name)
	logger.info('back to Psyllid interface')

	self.set_duration(run_time)
        if description!=None:
	    self.set_description(description)
	logger.info('starting run >{}>'.format(run_name))
        #if self.run_id is None:
        #    raise core.DriplineInternalError('run number is None, must request a run_id assignment prior to starting acquisition')

	filepath = "/".join([self.data_directory_path, '{:09d}'.format(self.run_id)])
	filename = "/{}{:09d}{}.egg".format(self.filename_prefix, self.run_id, run_name)
        if not os.path.exists(filepath):
            os.makedirs(filepath)
        self.set_path(filepath+filename)
	time.sleep(1)
	logger.info('Going to tell psyllid to start the run')
        result = self.provider.cmd(self.psyllid_queue, 'start-run')

        #else:
        #    self._acquisition_count += 1
	logger.info('run started')
        return "run {} started".format(run_name)


    def end_run(self):
        super(PsyllidAcquisitionInterface, self).end_run()
        result = self.provider.cmd(self.psyllid_queue, 'stop-run')
        logger.warning('daq stopped')


    #def stop_all(self):
    #    result = self.provider.cmd(self.psyllid_queue, 'stop-all')
    #    logger.info('all stopped')

    def quit_psyllid(self):
        result = self.provider.cmd(self.psyllid_queue, 'quit-psyllid')
        logger.info('psyllid quit')


#    def get_node(self):
#        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_GET, target=self.psyllid_queue+'.node'))
#        if result.retcode >= 100:
#            logger.warning('retcode indicates an error')
#        logger.info('node is {}'.format(result))

#    def set_node(self, node):
#        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[node]}), target=self.psyllid_queue+'.node'))
#        if result.retcode >= 100:
#            logger.warning('retcode indicates an error')
#        logger.info('node is {}'.format(result))


#    def start_roach2(self):
#        request = core.RequestMessage(msgop=core.OP_CMD)
#        result = self.portal.send_request(target=self.roach2_queue+'.configure_roach', request=request)
#        if result.retcode >= 100:
#            logger.warning('retcode indicates an error')
#        logger.info('The ROACH2 has been programmed succesfully: {}'.format(result.payload['values']))
#        return result.payload['values'][0]

#    def do_roach2_calibrations(self):
#        request = core.RequestMessage(msgop=core.OP_CMD)
#        result = self.portal.send_request(target=self.roach2_queue+'.do_adc_ogp_calibration', request=request)
#        if result.retcode >= 100:
#            logger.warning('retcode indicates an error')
#        logger.info('Doing adc and ogp calibration')
#        self.roach2calibrated=result.payload['values'][0]
#        return result.payload['values'][0]


