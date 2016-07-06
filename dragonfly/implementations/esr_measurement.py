from __future__ import absolute_import
__all__ = []

import dripline

import logging

import numpy

logger = logging.getLogger(__name__)


def lockin_result_to_array(result):
    return numpy.array(result.strip('\0').replace('\x00','').split(), dtype=float)

__all__.append('ESR_Measurement')
#@fancy_doc
class ESR_Measurement(dripline.core.Endpoint):
    """
        Operate the ESR system
    """
    def __init__(self,**kwargs):
        dripline.core.Endpoint.__init__(self,**kwargs)
        #We'll start with the things you should ever try to get
        self.status="done"
        self.resonant_frequency=0
        self.frequencies=[]
        self.amplitudes=[]
        self.filtered_data=[]
        self.bfield_1=0
        self.bfield_2=0
        self.bfield_3=0
        self.bfield_4=0
        self.bfield_5=0
        
        #these are not things in general you would get
        self.width=10.0e6; #resonance width in Hz, for a gaussian filter it is sigma, for a lorentzian it is FWMH
        self.start_freq=0; #sweeper start frequency
        self.stop_freq=0; #sweeper start frequency
        self.frequency_span=(self.stop_freq-self.start_freq)
        self.electron_cyclotron_frequency=1.758820024e11; # rad s^-1 T^-1
        self.esr_g_factor=1; #TODO look this up or put in config file, should be 2 something
        
    #call this with cmd
    def start_measurement(self,coilnum):
        self.status="not_done"
        #Make sure switches are in right configuration
        #TODO
        #Turn on sweeper
        self.set_ept('hf_start_freq',self.start_freq)
        self.set_ept('hf_stop_freq',self.stop_freq)
        #TODO pick power self.set('hf_power',???)
        self.set_ept('hf_output_status',1)
        self.frequency_span=(self.stop_freq-self.start_freq)
        #Activate lockin
        logger.info('ensure_setup')
        result=self.empty_get_ept('lockin_ensure_setup')
        logger.info('start_taking_data')
        result=self.empty_get_ept('lockin_take_data')
        isdone='running'
        while isdone=='running':
            isdone=self.raw_get_ept('lockin_status')[1]
            npts=self.raw_get_ept('lockin_curve_status')[1]
            logger.info('collected {}/400? points'.format(npts.split(',')[-1].strip()))
        #turn off the hf output
        self.set_ept('hf_output_status',0)
        #get the lockin data
        data={}

        data['amplitude']=lockin_result_to_array(self.raw_get_ept('lockin_mag_data')[0])
        data['sweep_out']=lockin_result_to_array(self.raw_get_ept('lockin_adc_data')[0])
        data['lockin_x_data']=lockin_result_to_array(self.raw_get_ept('lockin_x_data')[0])
        data['lockin_y_data']=lockin_result_to_array(self.raw_get_ept('lockin_y_data')[0])
        ten_volts=10.0
        data['frequencies'] = self.start_freq + frequency_span * data['sweep_out']/ten_volts
        data['amplitude'] = data['lockin_x_data'] + 1j*data['lockin_y_data']
        #Weiner filter
        filtered_data=WeinerFilter(data['frequencies'],data['amplitude'],self.width,'lorentzian')
        #find peak
        #TODO a fit would be more appropriate to get uncertainty
        max_freq_index = numpy.abs(filter_data['result']) == numpy.abs(filter_data['result']).max()
        res_freq = filter_data['freqs'][max_freq_index]
        #convert to field
        b_field=4.*scipy.pi*res_freq/(self.esr_g_factor*self.electron_cyclotron_frequency)
        self.resonant_frequency=res_freq
        self.frequencies=data['frequencies']
        self.amplitudes=data['amplitude']
        self.filtered_data=data['filtered_data']
        self.bfield_1=b_field
        self.bfield_2=b_field
        self.bfield_3=b_field
        self.bfield_4=b_field
        self.bfield_5=b_field

    def empty_get_ept(self, endptname):
        request_message = dripline.core.RequestMessage(msgop=dripline.core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)
        ret_rep=''
        if a_result.retcode !=0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)


    def get_ept(self, endptname):
        request_message = dripline.core.RequestMessage(msgop=dripline.core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)
        ret_rep=''
        if a_result.retcode !=0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
        else:
            ret_val = a_result.payload['value_cal']
        return ret_val,ret_rep

    def raw_get_ept(self, endptname):
        request_message = dripline.core.RequestMessage(msgop=dripline.core.OP_GET)
        a_result=self.portal.send_request(request=request_message,target=endptname)
        ret_rep=''
        if a_result.retcode !=0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
        else:
            ret_val = a_result.payload['values']
        return ret_val,ret_rep

    def set_ept(self,endptname,val):
        request_message = dripline.core.RequestMessage(msgop=dripline.core.OP_SET,
                                                       payload={'values':[val]})
        a_result=self.portal.send_request(request=request_message,target=endptname)
        if a_result.retcode !=0 :
            ret_val = None
            ret_rep = '{} -> returned error <{}>:{}'.format(endpoint_name, a_result.retcode, a_result.return_msg)
            logger.alert("got error "+ret_rep)
#        else:
#    ret_val = a_result.payload['value_cal']
#        return ret_val


def WeinerFilter(freq_data, amp_data, width, target='gaussian'):
    logger.warning('doing filter on target: {}'.format(target))
    data = zip(freq_data, amp_data)
    data.sort()
    f,v= zip(*data)
    frequencies = numpy.array(f, dtype=float)
    voltages = numpy.array(v, dtype=complex)
    x1 = (frequencies - frequencies[0])
    x2 = (frequencies - frequencies[-1])
    gderiv1 = x1 * numpy.exp(-x1**2 / 2. / width**2) / width
    gderiv2 = x2 * numpy.exp(-x2**2 / 2. / width**2) / width
    lderiv1 = -16. * x1 * width / (numpy.pi * (4*x1**2 + width**2))
    lderiv2 = -16. * x2 * width / (numpy.pi * (4*x2**2 + width**2))
    targets = {}
    targets['gaussian'] = numpy.concatenate((gderiv1[:len(gderiv1)/2], gderiv2[len(gderiv2)/2:]))
    targets['lorentzian'] = numpy.concatenate((lderiv1[:len(lderiv1)/2], lderiv2[len(lderiv2)/2:]))
    target_signal = targets[target]
    if not sum(target_signal != 0):
        raise ValueError("target signal identically 0, did you give width in Hz?")
    target_fft = numpy.fft.fft(target_signal)
    data_fft = numpy.fft.fft(voltages)
    data_fft[0] = 0
    filtered = numpy.fft.ifft(data_fft * target_fft)
    return {'freqs': frequencies,
            'result': abs(filtered),
            'target': target_signal
           }
