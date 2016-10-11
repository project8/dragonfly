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

from dripline.core import exceptions, fancy_doc
from dragonfly.implementations import EthernetProvider

from datetime import datetime
# from time import sleep

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
                 max_nb_files=10000,
                 trace_path=None,
                 **kwargs):
        EthernetProvider.__init__(self, **kwargs)
        if isinstance(trace_path,str):
            if trace_path.endswith("\"):
                self.trace_path = trace_path
            else:
                self.trace_path = trace_path + "\"
        else:
            logger.info("No trace_path given in the config file: save_trace feature disabled")
        self.max_nb_files = max_nb_files

    def save_trace(self, trace, additional_text):
        if self.trace_path is not None:
            logger.info('saving trace')
            filename = "{:%Y%m%d_%H%M%S}_Trace{}_{}".format(datetime.now(),trace,additional_text)
            path = self.trace_path + filename
            self.send(['MMEMory:DPX:STORe:TRACe{} "{}"; *OPC?'.format(trace,path)])
        else:
            logger.info("No trace_path given in the config file: save_trace feature disabled!")

    def create_new_auto_mask(self, trace, xmargin, ymargin):
        #This convenience method is currently broken
        logger.info('setting the auto mask')
        raise exceptions.DriplineError("convenience method <create_new_auto_mask> not yet implemented")
        self.provider.set('rsa_new_auto_mask','{},{},{}'.format(trace,xmargin,ymargin))

    @property
    def trigger_status(self):
        return self.send("TRIG:SEQUENCE:STATUS?")
    @trigger_status.setter
    def trigger_status(self, value):
        self.send("TRIG:SEQUENCE:STATUS {}; *OPC?".format(value))
        return self.send("TRIG:SEQUENCE:STATUS?")


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
        setattr(self, 'trigger_status', 1)

    def end_run(self):
        # disable the trigger mode
        setattr(self, 'trigger_status', 0)
        # disable the save dacq data on trigger mode
        self.send("TRIGger:SAVE:DATA 0;*OPC?")
