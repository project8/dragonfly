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
                                      payload={'values':[],
                                               'run_name':value,
                                              },
                                     )
        result = self.portal.send_request(self.run_table_endpoint+'.do_insert',
                                          request=request,
                                         )
        if not result.retcode == 0:
            raise core.exception_map[result.retcode](result.return_msg)
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
        self._run_meta = {'DAQ': self.daq_name,
                         }
        self._do_prerun_gets()
        if not self._debug_without_meta_broadcast:
            self._send_metadata()
        logger.debug('these meta will be {}'.format(self._run_meta))
        logger.info('start_run finished')

    def _do_prerun_gets(self):
        logger.info('doing prerun meta-data gets')
        query_msg = core.RequestMessage(msgop=core.OP_GET)
        these_metadata = {}
        result = self.portal.send_request(request=query_msg, target=self._metadata_state_target, timeout=120)
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
        request_msg = core.RequestMessage(payload=this_payload, msgop=core.OP_CMD)
        req_result = self.portal.send_request(request=request_msg, target=self._metadata_target)
        if not req_result.retcode == 0:
            raise core.exceptions.DriplineValueError('writing meta-data did not return success')
        logger.debug('meta sent')

    #TBD
    # def _send_daq_config(self):
    #     '''
    #     Save the daq configuration into a json file
    #     '''
    #     logger.info('{} config should broadcast'.format(self.daq_name))
    #     filename = '{directory}/{runN:09d}/{prefix}{runN:09d}_{daqname}_config.json'.format(
    #                                                     directory=self.meta_data_directory_path,
    #                                                     prefix=self.filename_prefix,
    #                                                     runN=self.run_id,
    #                                                     acqN=self._acquisition_count,
    #                                                     daqname=self.daq_name
    #                                                                            )
    #     logger.debug('should request daq config file: {}'.format(filename))
    #     this_payload = {'metadata': self._run_meta,
    #                     'filename': filename,
    #                    }
    #     this_payload['metadata']['run_id'] = self.run_id
    #     request_msg = core.RequestMessage(payload=this_payload, msgop=core.OP_CMD)
    #     req_result = self.portal.send_request(request=request_msg, target=self._metadata_target)
    #     if not req_result.retcode == 0:
    #         raise core.exceptions.DriplineValueError('writing meta-data did not return success')
    #     logger.debug('meta sent')

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

    @property
    def is_running(self):
        logger.info('query mantis server status to see if it is finished')
        result = self.portal.send_request(request=core.RequestMessage(msgop=core.OP_GET, payload={}), target=self.mantis_queue+'.server-status')
        to_return = True
        if result.payload['server']['server-worker']['status'] == u'Idle (queue is empty)':
            to_return = False
        return to_return

    def determine_RF_ROI(self):
        logger.info('trying to get roi')
        if not self._lf_lo_endpoint_name in self._run_meta:
            logger.error('meta are:\n{}'.format(self._run_meta))
            raise core.exceptions.DriplineInternalError('the lf_lo_endpoint_name must be configured in the metadata_gets field')
        lf_lo_freq = self._run_meta.pop(self._lf_lo_endpoint_name)
        self._run_meta['RF_ROI_MIN'] = float(lf_lo_freq) + float(self._hf_lo_freq)
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))
        self._run_meta['RF_ROI_MAX'] = float(self._analysis_bandwidth) + float(lf_lo_freq) + float(self._hf_lo_freq)
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
                 rsa_config_target='',
                 instrument_setup_filename_prefix=None,
                 mask_filename_prefix=None,
                #  roi_min_freq_endpoint_name=None,
                #  roi_max_freq_endpoint_name=None,
                 hf_lo_freq=24.2e9,
                 span_frequency_def_lab=None,
		         central_frequency_def_lab=None,
		         mask_ymargin_def_lab=None,
		         mask_xmargin_def_lab=None,
		         ref_level_def_lab=None,
		         source_event_def_lab=None,
		         type_event_def_lab=None,
		         violation_def_lab=None,
		         RBW_def_lab=None,
		         holdoff_def_lab=None,
		         holdoff_status_def_lab=None,
                 trig_delay_time_def_lab=None,
                 trig_delay_pos_def_lab=None,
                 trig_time_qualification_def_lab=None,
                 internal_attenuator_def_lab=None,
                 internal_attenuator_auto_def_lab=None,
		         osc_source_def_lab='EXT',
		         max_nb_files=10000,
                 **kwargs):
        DAQProvider.__init__(self, **kwargs)
        EthernetProvider.__init__(self, **kwargs)
        self.rsa_config_target=rsa_config_target

        if hf_lo_freq is None:
            raise core.exceptions.DriplineValueError('the rsa interface requires a "hf_lo_freq"')
        self._hf_lo_freq = hf_lo_freq
        # if roi_min_freq_endpoint_name is None:
        #     raise core.exceptions.DriplineValueError('the rsa interface requires a "roi_min_freq_endpoint_name"')
        # self._roi_min_freq_endpoint_name = roi_min_freq_endpoint_name
        # if roi_max_freq_endpoint_name is None:
        #     raise core.exceptions.DriplineValueError('the rsa interface requires a "roi_max_freq_endpoint_name"')
        # self._roi_max_freq_endpoint_name = roi_max_freq_endpoint_name

        self.max_nb_files = max_nb_files
        self.span_frequency_def_lab = span_frequency_def_lab
        self.central_frequency_def_lab = central_frequency_def_lab
        self.mask_ymargin_def_lab = mask_ymargin_def_lab
        self.mask_xmargin_def_lab = mask_xmargin_def_lab
        self.ref_level_def_lab = ref_level_def_lab
        self.source_event_def_lab = source_event_def_lab
        self.type_event_def_lab = type_event_def_lab
        self.violation_def_lab = violation_def_lab
        self.RBW_def_lab = RBW_def_lab
        self.holdoff_def_lab = holdoff_def_lab
        self.holdoff_status_def_lab = holdoff_status_def_lab
        self.trig_delay_time_def_lab = trig_delay_time_def_lab
        self.trig_delay_pos_def_lab = trig_delay_pos_def_lab
        self.trig_time_qualification_def_lab = trig_time_qualification_def_lab
        self.internal_attenuator_auto_def_lab = internal_attenuator_auto_def_lab
        self.internal_attenuator_def_lab = internal_attenuator_def_lab
        self.osc_source_def_lab = osc_source_def_lab

    @property
    def is_running(self):
        logger.info('query RSA trigger status')
        result = self.send(['TRIG:SEQ:STAT?'])
        to_return = None
        if result== '0':
            to_return = False
        elif result == '1':
            to_return = True
        else:
            raise ValueError('unrecognized return value')
        logger.info('trigger status is <{}>'.format(to_return))
        return to_return

    def set_default_config(self):
        logger.info('setting default config for data taking')

        logger.info('getting all the lastest errors in the system and purging the queue')
        errors = self.send(['SYSTEM:ERROR:ALL?'])

        logger.info('setting frequencies')
        self.set_central_frequency(self.central_frequency_def_lab)
        self.set_frequency_span(self.span_frequency_def_lab)
        # self.send(['DPX:FREQ:CENT {};*OPC?'.format(self.central_frequency_def_lab)])
        # self.send(['DPX:FREQ:SPAN {};*OPC?'.format(self.span_frequency_def_lab)])

        logger.info('setting reference level')
        self.set_reference_level(self.ref_level_def_lab)
        # self.send(['INPUT:RLEVEL {};*OPC?'.format(self.ref_level_def_lab)])

        logger.info('setting resolution bandwidths')
        self.set_resolution_bandwidth(self.RBW_def_lab)
        # self.send(['DPX:BWID:RES {};*OPC?'.format(self.RBW_def_lab)])

        logger.info('setting source of events')
        self.set_event_source(self.source_event_def_lab)
        # self.send(['TRIG:EVEN:SOUR {};*OPC?'.format(self.source_event_def_lab)])

        logger.info('setting type of events')
        self.set_event_type(self.type_event_def_lab)
        # self.send(['TRIG:EVEN:INP:TYPE {};*OPC?'.format(self.type_event_def_lab)])

        logger.info('setting trigger violation condition')
        self.set_trig_violation_condition(self.violation_def_lab)
        # self.send(['TRIG:EVEN:INP:FMASk:VIOL {};*OPC?'.format(self.violation_def_lab)])

        logger.info('setting trigger holdoff')
        self.set_trigger_holdoff(self.holdoff_def_lab)
        # self.send(['TRIG:ADV:HOLD {};*OPC?'.format(self.holdoff_def_lab)])

        logger.info('setting trigger holdoff status')
        self.set_trigger_holdoff_status(self.holdoff_status_def_lab)
        # self.send(['TRIG:ADV:HOLD:ENABle {};*OPC?'.format(self.holdoff_status_def_lab)])

        logger.info('setting trigger delay time')
        self.set_trigger_delay_time(self.trig_delay_time_def_lab)
        # self.send(['TRIGGER:SEQUENCE:TIME:DELAY {};*OPC?'.format(self.trig_delay_time_def_lab)])

        logger.info('setting trigger delay position')
        self.set_trigger_delay_position(self.trig_delay_pos_def_lab)
        # self.send(['TRIGGER:SEQUENCE:TIME:POSITION {};*OPC?'.format(self.trig_delay_pos_def_lab)])

        logger.info('setting trigger time qualification')
        self.set_trigger_time_qualification(self.trig_time_qualification_def_lab)
        # self.send(['TRIGger:SEQuence:TIME:QUALified {};*OPC?'.format(self.trig_time_qualification)])

        logger.info('setting internal attenuator auto mode')
        self.set_internal_attenuator_auto(self.internal_attenuator_auto_def_lab)
        # self.send(['INPUT:RF:ATTENUATION:AUTO {};*OPC?'.format(self.internal_attenuator_auto_def_lab)])

        logger.info('setting internal attenuator')
        self.set_internal_attenuator(self.internal_attenuator_def_lab)
        # self.send(['INPUT:RF:ATTENUATION {};*OPC?'.format(self.internal_attenuator_def_lab)])

        logger.info('setting oscillator source')
        self.set_osc_source(self.osc_source_def_lab)
        # self.send(['SENSE:ROSCILLATOR:SOURCE {};*OPC?'.format(self.osc_source_def_lab)])

        logger.info('setting new mask auto')
        self.create_new_auto_mask('TRACE3',self.mask_xmargin_def_lab,self.mask_ymargin_def_lab)
        # self.send(['TRIG:MASK:NEW:AUTO "dpsa",TRACE3,{},{};*OPC?'.format(self.mask_xmargin_def_lab,self.mask_ymargin_def_lab)])

    def set_central_frequency(self,central_frequency):
        logger.info('setting central frequency')
        self.send(['DPX:FREQ:CENT {};*OPC?'.format(central_frequency)])

    def set_frequency_span(self,frequency_span):
        logger.info('setting frequency span')
        self.send(['DPX:FREQ:SPAN {};*OPC?'.format(frequency_span)])

    def set_reference_level(self,ref_level):
        logger.info('setting reference level')
        self.send(['INPUT:RLEVEL {};*OPC?'.format(ref_level)])

    def set_event_source(self,event_source):
        logger.info('setting event source')
        self.send(['TRIG:EVEN:SOUR {};*OPC?'.format(event_source)])

    def set_event_type(self,event_type):
        logger.info('setting event type')
        self.send(['TRIG:EVEN:INP:TYPE {};*OPC?'.format(event_type)])

    def set_trig_violation_condition(self,trig_viol):
        logger.info('setting trigger violation')
        self.send(['TRIG:EVEN:INP:FMASk:VIOL {};*OPC?'.format(trig_viol)])

    def set_resolution_bandwidth(self,rbw):
        logger.info('setting resolution bandwidths')
        self.send(['DPX:BWID:RES {};*OPC?'.format(rbw)])

    def set_config_from_file(self,file_path):
        logger.info('setting instrument config from file')
        if file_path is None:
            raise core.DriplineInternalError('no file_path was given')
        self.send('MMEMory:LOAD:STATe "{}"; OPC?'.format(file_path))

    def set_trigger_holdoff(self,value):
        logger.info('setting trigger holdoff')
        self.send(['TRIG:ADV:HOLD {};*OPC?'.format(value)])

    def set_trigger_holdoff_status(self,value):
        logger.info('setting trigger holdoff status')
        self.send(['TRIG:ADV:HOLD:ENABle {};*OPC?'.format(value)])

    def set_trigger_delay_time(self,value):
        logger.info('setting trigger delay time')
        self.send(['TRIGGER:SEQUENCE:TIME:DELAY {};*OPC?'.format(value)])

    def set_trigger_delay_position(self,value):
        logger.info('setting trigger delay position')
        self.send(['TRIGGER:SEQUENCE:TIME:POSITION {};*OPC?'.format(value)])

    def set_trigger_status(self,value):
        logger.info('setting trigger status')
        if value == 1 or value == 'on' or value == 'enable':
            self.send(['TRIG:SEQUENCE:STATUS 1;*OPC?'.format(value)])
        elif value == 0 or value == 'off' or value == 'disable':
            self.send(['TRIG:SEQUENCE:STATUS 0;*OPC?'.format(value)])
        else:
            core.DriplineInternalError('invalid given parameter ({}) instead of 1/on/enable/0/off/disable'.format(value))

    def set_trigger_time_qualification(self,value):
        logger.info('setting trigger time qulification')
        if value == 'SHOR' or value == 'LONG' or value == 'INS' or value == 'OUT' or value == 'NONE':
            self.send(['TRIGger:SEQuence:TIME:QUALified {};*OPC?'.format(value)])
        else:
            core.DriplineInternalError('invalid given parameter ({}) instead of SHOR/LONG/INS/OUT/NONE'.format(value))

    def set_osc_source(self,value):
        logger.info('setting oscillator source')
        if value == 'INT' or value == 'EXT':
            self.send(['SENSE:ROSCILLATOR:SOURCE {};*OPC?'.format(value)])
        else:
            core.DriplineInternalError('invalid given parameter ({}) instead of EXT/INT'.format(value))

    def set_internal_attenuator(self,value):
        logger.info('setting internal attenuator')
        self.send(['INPUT:RF:ATTENUATION {};*OPC?'.format(value)])

    def set_internal_attenuator_auto(self,value):
        if value == 1 or value == 'on' or value == 'enable':
            self.send(['INPUT:RF:ATTENUATION:AUTO 1;*OPC?'.format(value)])
        elif value == 0 or value == 'off' or value == 'disable':
            self.send(['INPUT:RF:ATTENUATION:AUTO 0;*OPC?'.format(value)])
        else:
            core.DriplineInternalError('invalid given parameter ({}) instead of 1/on/enable/0/off/disable'.format(value))

    def create_new_auto_mask(self, trace, xmargin, ymargin):
        logger.info('setting the auto mask')
        # if trace == 'TRACE1' or trace == 'trace1':
        self.send(['TRIG:MASK:NEW:AUTO "dpsa",{},{},{};*OPC?'.format(trace,xmargin,ymargin)])

    def start_run(self, run_name):
        # try to force external reference
        self.send(['SENS:ROSC:SOUR EXT;*OPC?'])
        the_ref = self.send(['SENS:ROSC:SOUR?'])
        if the_ref != 'EXT\n' and the_ref != 'EXT':
            raise core.exceptions.DriplineHardwareError('RSA external ref found to be <{}> (!="EXT")'.format(the_ref))

        # counting the number of errors in the RSA system queue and aborting the data taking if Nerrors>0
        Nerrors = self.send(['SYSTEM:ERROR:COUNT?'])
        if Nerrors!='0':
            raise core.exceptions.DriplineHardwareError('RSA system has {} error(s) in the queue: check them with <dragonfly get rsa_system_error_queue -b myrna.p8>'.format(Nerrors))

        super(RSAAcquisitionInterface, self).start_run(run_name)
        # ensure the output format is set to mat
        self.send(["SENS:ACQ:FSAV:FORM MAT;*OPC?"])
        # build strings for output directory and file prefix, then set those
        file_directory = "\\".join([self.data_directory_path, '{:09d}'.format(self.run_id)])
        file_base = "{}{:09d}".format(self.filename_prefix, self.run_id)
        self.send('SENS:ACQ:FSAV:LOC "{}";*OPC?'.format(file_directory))
        self.send('SENS:ACQ:FSAV:NAME:BASE "{}";*OPC?'.format(file_base))

        # Set the maximum number of events (note that the default is 10k)
        self.send(['SENS:ACQ:FSAV:FILE:MAX {:d};*OPC?'.format(self.max_nb_files)])

        # saving the instrument status in hot
        instrument_status_full_name = '{directory}/{prefix}{runN:09d}'.format(
                                                        directory=file_directory,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id
                                                                               )
        self.send(['MMEM:STOR:STAT "{}";*OPC?'.format(instrument_status_full_name)])
        # saving the frequency mask in hot
        mask_full_name = '{directory}/{prefix}{runN:09d}'.format(
                                                        directory=file_directory,
                                                        prefix=self.filename_prefix,
                                                        runN=self.run_id
                                                                               )
        self.send(['TRIG:MASK:SAVE "{}";*OPC?'.format(mask_full_name)])

        # ensure in triggered mode
        self.send(['TRIG:SEQ:STAT 1;*OPC?'])
        # actually start to FastSave (depreciated)
        # self.send(['SENS:ACQ:FSAV:ENAB 1;*OPC?'])

    def end_run(self):
        # something to stop FastSave (depreciated)
        # self.send(['SENS:ACQ:FSAV:ENAB 0;*OPC?'])
        self.send(['TRIG:SEQ:STAT 0;*OPC?'])
        super(RSAAcquisitionInterface, self).end_run()


    def determine_RF_ROI(self):
        logger.info('trying to determine roi')
        # logger.warning('RSA does not support proper determination of RF ROI yet')

        self._run_meta['RF_ROI_CENTER'] = float(self._hf_lo_freq)
        logger.debug('RF Central: {}'.format(self._run_meta['RF_ROI_CENTER']))

        result = self.send(['DPX:FREQ:START?'])
        self._run_meta['RF_ROI_MIN'] = float(result) + float(self._hf_lo_freq)
        logger.debug('RF Min: {}'.format(self._run_meta['RF_ROI_MIN']))
        
        result = self.send(['DPX:FREQ:STOP?'])
        self._run_meta['RF_ROI_MAX'] = float(result) + float(self._hf_lo_freq)
        logger.debug('RF Max: {}'.format(self._run_meta['RF_ROI_MAX']))
