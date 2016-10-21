'''
'''

from __future__ import absolute_import

# standard imports
import logging
import uuid
import time
import os

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
                 metadata_state_target='',
                 metadata_target='',
                 debug_mode_without_database=False,
                 debug_mode_without_metadata_broadcast=False,
                 **kwargs):
        '''
        daq_name (str): name of the DAQ (used with the run table and in metadata)
        run_table_endpoint (str): name of the endpoint providing an interface to the run table
        directory_path (str): absolute path to "hot" storage (as seen from the DAQ software, not a network path)
        meta_data_directory_path (str): path where the metadata file should be written
        filename_prefix (str): prefix for unique filenames
        metadata_state_target (str): multiget endpoint to Get() for system state
        metadata_target (str): target to send metadata to
        debug_mode_without_database (bool): if True, forces a run_id of 0, rather that making a query (should only be True as part of debugging)
        debug_mode_without_metadata_broadcast (bool): if True, skips the step of sending metadata to the metadata receiver (should only be True as part of debugging)
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

        #self._metadata_gets = metadata_gets
        self._metadata_state_target = metadata_state_target
        self._metadata_target = metadata_target
        self.filename_prefix = filename_prefix
        self._debug_without_db = debug_mode_without_database
        self._debug_without_meta_broadcast = debug_mode_without_metadata_broadcast

        self._stop_handle = None
        self._run_name = None
        self.run_id = None
        self._acquisition_count = None

        print('no errors from DAQ Provider')

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
        result = self.provider.cmd(self.run_table_endpoint, 'do_insert', payload={'run_name':value})
        self.run_id = result['run_id']

    def end_run(self):
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
                         }

        self._do_prerun_gets()
        if not self._debug_without_meta_broadcast:
            self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')

    def _do_prerun_gets(self):
        logger.info(self._metadata_state_target)
        logger.info('doing prerun meta-data gets')
        #result = self.provider.get(self._metadata_state_target, timeout=120)
        query_msg = core.RequestMessage(msgop=core.OP_GET)
        result = self.portal.send_request(request=query_msg, target=self._metadata_state_target, timeout=100)
        logger.info(result.payload)
        these_metadata = result.payload['value_raw']
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
        logger.debug('should request metadatafile: {}'.format(filename))
        this_payload = {'metadata': self._run_meta,
                        'filename': filename,
                       }
        this_payload['metadata']['run_id'] = self.run_id
        # note, the following line has an empty method/RKS, this shouldn't be the case but is what golang expects
        req_result = self.provider.cmd(self._metadata_target, None, payload=this_payload)
        logger.debug('meta sent')

    def start_timed_run(self, run_name, run_time):
        '''
        '''
        self._stop_handle = self.service._connection.add_timeout(int(run_time), self.end_run)
        self.start_run(run_name)


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
                 **kwargs):
        DAQProvider.__init__(self, **kwargs)

        if daq_target is None:
            raise core.exceptions.DriplineValueError('the rsa acquisition interface requires a valid "daq_target" in its config file')
        self._daq_target = daq_target
        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the rsa acquisition interface requires a "hf_lo_freq" in its config file')
        self._hf_lo_freq = hf_lo_freq

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


__all__.append('PsyllidAcquisitionInterface')
class PsyllidAcquisitionInterface(DAQProvider, core.Spime):
    '''
    A DAQProvider for interacting with Psyllid DAQ
    '''
    def __init__(self,
                 psyllid_queue='psyllid',
                 roach2_queue = 'roach2_interface',
                 psyllid_preset = 'str-1ch',
                 udp_receiver_port = 23530,
                 timeout = 10,
                 **kwargs
                ):

        DAQProvider.__init__(self, **kwargs)
        core.Spime.__init__(self, **kwargs)
        self.alert_routing_key = 'daq_requests'

        self.psyllid_queue = psyllid_queue
        self.roach2_queue = roach2_queue
        self.timeout = timeout


        self.status = None
        self.status_value = None
	self.duration = None
        self.psyllid_preset = psyllid_preset
        self.udp_receiver_port = udp_receiver_port




    def _finish_configure(self):
        logger.debug('Configuring Psyllid')
        is_running = self.is_running()
        if is_running:
            if self.status_value == 4:
                self.deactivate()
                #self.is_running()

            elif self.status_value!=0:
                raise core.DriplineInternalError('Status of Psyllid must be "Initialized", status is {}'.format(self.status))

            #set daq presets
            self.configure(self.psyllid_preset)

            #set udp receiver port
            self.set_udp_port(self.udp_receiver_port)

            #activate
            self.activate()
            return True

        else:
            logger.error('Psyllid could not be configured.')
            return False



    def is_running(self):
        logger.info('Checking Psyllid status')
        query_msg = core.RequestMessage(msgop=core.OP_GET)

        try:
            result = self.portal.send_request(request=query_msg, target=self.psyllid_queue+'.daq-status', timeout=self.timeout)
            #result = self.provider.cmd(self.psyllid_queue, 'daq-status', payload={})

            if result.retcode >= 100:
                logger.warning('retcode indicates an error')
                self.status=None
                self.status_value=None
                return False

            self.status = result.payload['server']['status']
            self.status_value = result.payload['server']['status-value']
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
        logger.info('Setting udp receiver port to {}'.format(new_port))
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[new_port]}), target=self.psyllid_queue+'.node.udpr.port')
        if result.retcode >= 100:
            logger.warning('retcode from udpr.port indicates an error')

    def get_udp_port(self):
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_GET), target=self.psyllid_queue+'.node.udpr.port')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        logger.info('udp receiver port is: {}'.format(result.payload))
        return self.udp_receiver_port

    def set_path(self, filepath):

        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[filepath]}), target=self.psyllid_queue+'.filename')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        self.get_path()

    def get_path(self):
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_GET), target=self.psyllid_queue+'.filename')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        logger.info('Egg filename is {} path is {}'.format(result.payload['values'], self.data_directory_path))
        return result.payload['values']

    def change_data_directory_path(self,path):
        self.data_directory_path = path
        return path

    def set_description(self, description):
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[description]}), target=self.psyllid_queue+'.description')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        logger.info('Description set to:'.format(description))

    def get_description(self):
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_GET), target=self.psyllid_queue+'.description')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        logger.info('Description is {}:'.format(result.payload))

    def set_duration(self, duration):
        #self.acquisition_time(duration)
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[duration]}), target=self.psyllid_queue+'.duration')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
	self.duration = duration

    def get_duration(self):
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_GET), target=self.psyllid_queue+'.duration')
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
        logger.info('Duration is {}'.format(result.payload))
        return result.payload['values'][0]




    @property
    def acquisition_time(self):
        return self.log_interval
    @acquisition_time.setter
    def acquisition_time(self, value):
        self.log_interval = value


    #other methods

    def configure(self,config=None):
        if config == None:
            config = self.psyllid_preset
        logger.info('Configuring Psyllid with {}'.format(config))
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[config]}), target=self.psyllid_queue+'.daq-preset')

        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
	    return False
	else:
	    return True

    def activate(self):
        if self.status_value == 6:
            self.is_running()
        elif self.status_value == 0:
            logger.info('Activating Psyllid')
            request = core.RequestMessage(msgop=core.OP_CMD)
            result = self.portal.send_request(target=self.psyllid_queue+'.activate-daq', request=request, timeout=self.timeout)
            if result.retcode >= 100:
                logger.warning('retcode indicates an error')
            #self.is_running()
            time.sleep(1)
            self.is_running()
            return True

        else:
            logger.warning('Could not activate Psyllid')
            return False


    def deactivate(self):
        if self.status != 0:
            logger.info('Deactivating Psyllid')
            request = core.RequestMessage(msgop=core.OP_CMD)
            result = self.portal.send_request(target=self.psyllid_queue+'.deactivate-daq', request=request, timeout=self.timeout)
            if result.retcode >= 100:
                logger.warning('retcode indicates an error')
            time.sleep(1)
            self.is_running()
            return True

        else:
            logger.info('Could not deactivate Psyllid')
            return False


    def check_roach2_status(self):

        #call is_running
        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(target=self.roach2_queue+'.is_running', request=request)
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')
            return False

        elif result.payload['values'][0]==False:
            logger.warning('The ROACH2 is not running!')
            return False


        elif result.payload['values'][0]==True:

            #get calibration and configuration status
            request = core.RequestMessage(msgop=core.OP_CMD)
            result = self.portal.send_request(target=self.roach2_queue+'.get_calibration_status', request=request)
            if result.retcode >= 100:
                logger.warning('retcode indicates an error')
            self.roach2calibrated=result.payload['values'][0]

            request = core.RequestMessage(msgop=core.OP_CMD)
            result = self.portal.send_request(target=self.roach2_queue+'.get_configuration_status', request=request)
            if result.retcode >= 100:
                logger.warning('retcode indicates an error')
            self.roach2configured=result.payload['values'][0]

            #print results
            logger.info('Configured: {}, Calibrated: {}'.format(self.roach2configured, self.roach2calibrated))

            return True
        else:
            return False


    def determine_RF_ROI(self):
        logger.info('trying to determine roi')
        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(target=self.roach2_queue+'.get_central_frequency', request=request)
        if result.retcode >= 100:
            logger.warning('retcode indicates an error')

        logger.info('Central frequency is: {}'.format(result.payload['values'][0]))
        return result.payload['values'][0]


    def start_run(self, run_name):
        logger.info('Starting run. Psyllid status is {}'.format(self.status))

        #checking psyllid
        if self.status_value == None:
            logger.warning('Psyllid was not configured')

            if not self._finish_configure():
                logger.error('Problem could not be solved by (re-)configuring Psyllid')
                return 'Psyllid is not running'

        #checking roach
        if self.roach2_queue!=None:
            result=self.check_roach2_status()
            if result != True:
                logger.error('Psyllid and the ROACH2 are not connected')
                return 'False'
            elif self.roach2calibrated == False:
                logger.warning('adc and ogp calibration has not been performed yet.')


        logger.info('runname is {}'.format(run_name))
	self.set_duration(self.log_interval)
        
	super(PsyllidAcquisitionInterface, self).start_run(run_name)

        self.on_get()
        self.logging_status = 'on'


    def start_timed_run(self, run_name, run_time):
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
        is_roach_running = self.check_roach2_status
        if is_roach_running == False:
            return False

        elif is_roach_running == True:
            if self.roach2configured ==False:
                logger.warning('The ROACH2 might not be configured correctly. Check Roach2 service')
            if self.roach2calibrated==False:
                logger.warning('The adc is not calibrated. Data taking not recommended.')

        logger.info('runname is {}'.format(run_name))
        super(PsyllidAcquisitionInterface, self).start_run(run_name)

#        num_acquisitions = int(run_time // self.acquisition_time)
#        last_run_time = run_time % self.acquisition_time
#        logger.info("going to request <{}> runs, then one of <{}> [s]".format(num_acquisitions, last_run_time))

	self.set_duration(run_time)
#        for acq in range(num_acquisitions):
#            self.on_get()
#        if last_run_time != 0:
#            self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[last_run_time*1000]}), target=self.psyllid_queue+'.duration')
#            self.on_get()
#            self.portal.send_request(request=core.RequestMessage(msgop=core.OP_SET, payload={'values':[self.acquisition_time*1000]}), target=self.psyllid_queue+'.duration')
        logger.info('starting run >{}>'.format(run_name))
        if self.run_id is None:
            raise core.DriplineInternalError('run number is None, must request a run_id assignment prior to starting acquisition')
        filepath = '{directory}/'.format(
                                        directory=self.data_directory_path)

        filename = '{prefix}{runN:09d}_{acqN:09d}_{runname}.egg'.format(prefix=self.filename_prefix,
                                        runN=self.run_id,
                                        acqN=self._acquisition_count,
					runname=run_name)

        if not os.path.exists(filepath):
            os.makedirs(filepath)
        self.set_path(filepath+filename)
	time.sleep(1)

        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(self.psyllid_queue+'.start-run',
                                          request=request,
                                          timeout=self.timeout)
        if result.retcode != 0:
	    logger.warning(result.payload)
            self.end_run()

        else:
            self._acquisition_count += 1
	    logger.info('run started')
            return "run {} started".format(run_name)



    def on_get(self):
        '''
        Setting an on_get so that the logging functionality can be used to queue multiple acquisitions.
        '''
        logger.info('requesting acquisition <{}>'.format(self._acquisition_count))
        if self.run_id is None:
            raise core.DriplineInternalError('run number is None, must request a run_id assignment prior to starting acquisition')
        filepath = '{directory}/'.format(
                                        directory=self.data_directory_path)

        filename = '{prefix}{runN:09d}_{acqN:09d}.egg'.format(prefix=self.filename_prefix,
                                        runN=self.run_id,
                                        acqN=self._acquisition_count)

        if not os.path.exists(filepath):
            os.makedirs(filepath)

        self.set_path(filepath+filename)


        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(self.psyllid_queue+'.start-run',
                                          request=request,
                                         )
        if not result.retcode == 0:
            msg = ''
            if 'ret_mes' in result.payload:
                msg = result.payload['ret_mes']
            logger.warning('Got an error from psyllid. Return code: {}, Return message: {}, stopping run.'.format(result.retcode, msg))
            #self.end_run()

        else:
            self._acquisition_count += 1
            return "acquisition of [{}] requested".format(filename)


    def end_run(self):
        self.logging_status = 'stop'
        super(PsyllidAcquisitionInterface, self).end_run()
        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(target=self.psyllid_queue+'.stop-run', request=request)
        if not result.retcode == 0:
            logger.warning('error stoping daq:\n{}'.format(result.return_msg))
        else:
            logger.warning('daq stopped')
        #self.deactivate()
        #if not result.retcode == 0:
        #    logger.warning('error stopping daq:\n{}'.format(result.return_msg))
        #self.activate()
        #if not result.retcode == 0:
        #    logger.warning('error restarting queue:\n{}'.format(result.return_msg))

        self._acquisition_count = 0


    def stop_all(self):
        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(target=self.psyllid_queue+'.stop-all', request=request)
        logger.info('all stopped')

    def quit_psyllid(self):
        request = core.RequestMessage(msgop=core.OP_CMD)
        result = self.portal.send_request(target=self.psyllid_queue+'.quit-psyllid', request=request)
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


#    def connect2roach2(self):
#
#        result = self.check_on_roach2()
#
#        if result is True:
#
#            if self.roach2configured is False:
#                self.start_roach2()
#
#            return True
#
#        elif result==False:
#            logger.info('Could not connect to the ROACH2')
#            return False
#
#        else:
#            logger.warning('The ROACH2 service is not running or sth. else is wrong')
##            self.roach2_queue=None
#            return False
