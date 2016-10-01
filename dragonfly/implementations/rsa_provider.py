'''
The RSAProvider is designed to inherit from EthernetProvider and provide communication with the RSA instrument.
Methods contained here were carefully selected to protect the user
- they combine multiple send calls which only make sense when called in concert
- they ARE NOT endpoints because using the individual commands would be potentially dangerous
- expect them to be implemented by RSAAcquisitionInterface via provider.cmd

The two exceptions are the methods which require multiple arguments, which are not handled simply with `dragonfly set` commands:
- save_trace(self, trace, path)
- create_new_auto_mask(self, trace, xmargin, ymargin)

Everything else should be defined as a normal endpoint in the config file.
If you a send call here that you would like to see as an endpoint, try to think of how that would go wrong before implementing it blindly.
'''

from __future__ import absolute_import

#from dripline.core import Endpoint, exceptions, calibrate
from dragonfly.implementations import EthernetProvider

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('RSAProvider')
@fancy_doc
class RSAProvider(EthernetProvider):
    '''
    An EthernetProvider for interacting with the RSA (Tektronix 5106B)
    '''
    def __init__(self,
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
                 acquisition_mode_def_lab=None,
                 acquisition_length_def_lab=None,
 		         osc_source_def_lab='EXT',
 		         max_nb_files=10000,
                 **kwargs):
        EthernetProvider.__init__(self, **kwargs)

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
        self.acquisition_mode = acquisition_mode_def_lab
        self.acquisition_length = acquisition_length_def_lab
        self.osc_source_def_lab = osc_source_def_lab

    def set_default_config(self):
        logger.info('setting default config for data taking')

        logger.debug('getting all the lastest errors in the system and purging the queue')
        errors = self.provider.get("rsa_system_error_queue")
        logger.warning(errors)

        logger.debug('setting central frequency')
        self.provider.set('rsa_central_frequency', self.central_frequency_def_lab)

        logger.debug('setting frequency span')
        self.provider.set('rsa_frequency_span', self.span_frequency_def_lab)

        logger.debug('setting reference level')
        self.provider.set('rsa_reference_level', self.ref_level_def_lab)

        logger.debug('setting resolution bandwidths')
        self.provider.set('rsa_resolution_bandwidth', self.RBW_def_lab)

        logger.debug('setting source of events')
        self.provider.set('rsa_event_source', self.source_event_def_lab)

        logger.debug('setting type of events')
        self.provider.set('rsa_event_type', self.type_event_def_lab)

        logger.debug('setting trigger violation condition')
        self.provider.set('rsa_trigger_violation_condition', self.violation_def_lab)

        logger.debug('setting trigger holdoff')
        self.provider.set('rsa_trigger_holdoff', self.holdoff_def_lab)

        logger.debug('setting trigger holdoff status')
        self.provider.set('rsa_trigger_holdoff_status', self.holdoff_status_def_lab)

        logger.debug('setting trigger delay time')
        self.provider.set('rsa_trigger_delay_time', self.trig_delay_time_def_lab)

        logger.debug('setting trigger delay position')
        self.provider.set('rsa_trigger_delay_position', self.trig_delay_pos_def_lab)

        logger.debug('setting trigger time qualification')
        self.provider.set('rsa_trigger_time_qualification', self.trig_time_qualification_def_lab)

        logger.debug('setting internal attenuator auto mode')
        self.provider.set('rsa_internal_attenuator_auto', self.internal_attenuator_auto_def_lab)

        logger.debug('setting internal attenuator')
        self.provider.set('rsa_internal_attenuator', self.internal_attenuator_def_lab)

        logger.debug("setting acquisition mode")
        self.provider.set('rsa_acquisition_mode', self.acquisition_mode_def_lab)

        logger.debug("setting acquisition length")
        self.provider.set('rsa_acquisition_length', self.acquisition_length_def_lab)

        logger.debug('setting oscillator source')
        self.provider.set('rsa_osc_source', self.osc_source_def_lab)

        logger.debug('setting new mask auto')
        self.create_new_auto_mask('TRACE3',self.mask_xmargin_def_lab,self.mask_ymargin_def_lab)

    def save_trace(self, trace, path):
        logger.info('saving trace')
        self.send(['MMEMory:DPX:STORe:TRACe{} "{}"; *OPC?'.format(trace,path)])

    def create_new_auto_mask(self, trace, xmargin, ymargin):
        logger.info('setting the auto mask')
        self.provider.set('rsa_new_auto_mask','{},{},{}'.format(trace,xmargin,ymargin))


    def ensure_ready_state(self):
        # try to force external reference
        the_ref = self.provider.set('rsa_osc_source', 'EXT')['value_raw']
        if the_ref != 'EXT':
            raise core.exceptions.DriplineHardwareError('RSA external ref found to be <{}> (!="EXT")'.format(the_ref))

        # counting the number of errors in the RSA system queue and aborting the data taking if Nerrors>0
        Nerrors = self.provider.get('rsa_system_error_count')['value_raw']
        if Nerrors != '0':
            raise core.exceptions.DriplineHardwareError('RSA system has {} error(s) in the queue: check them with <dragonfly get rsa_system_error_queue -b myrna.p8>'.format(Nerrors))

    def start_run(self, directory, filename):
        # set output directory and file prefix
        self.send('SENS:ACQ:FSAV:LOC "{}";*OPC?'.format(directory))
        self.send('SENS:ACQ:FSAV:NAME:BASE "{}";*OPC?'.format(filename))
        # ensure the output format is set to mat
        self.send('TRIGger:SAVE:DATA:FORMat MAT;*OPC?')
        # ensure their is no limit on the number of saved files
        self.send("TRIGger:SAVE:COUNt 0; *OPC?")

        # Set the maximum number of events (note that the default is 10k)
        self.send(['SENS:ACQ:FSAV:FILE:MAX {:d};*OPC?'.format(self.max_nb_files)])

        full_name = "{}/{}".format(directory, filename)
        # saving the instrument status in hot
        self.send(['MMEM:STOR:STAT "{}";*OPC?'.format(full_name)])
        # saving the frequency mask in hot
        self.send(['TRIG:MASK:SAVE "{}";*OPC?'.format(full_name)])

        # enable the save dacq data on trigger mode
        self.send("TRIGger:SAVE:DATA 1;*OPC?")
        # ensure in triggered mode
        self.provider.set('rsa_trigger_status', 1)

    def end_run(self):
        # disable the trigger mode
        self.provider.set('rsa_trigger_status', 0)
        # disable the save dacq data on trigger mode
        self.send("TRIGger:SAVE:DATA 0;*OPC?")
