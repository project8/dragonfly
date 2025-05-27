'''
Implementation of a PID control loop for a TCP server as a workaround
'''

from __future__ import print_function
__all__ = []
import time
import datetime
from simple_pid import PID
import connection as con
import json


import logging
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())

__all__.append('PidController')
class PidController():
    '''
    Implementation of a PID control loop with constant offset. That is, the PID equation
    is used to compute the **change** to the value of some channel and not the value
    itself. In the case of temperature control, this makes sense if the loop is working
    against some fixed load (such as a cryocooler).

    The input sensor can be anything which broadcasts regular values on the alerts
    exchange (using the standard sensor_value.<name> routing key format). Usually
    this would be a temperature sensor, but it could be anything. Similarly, the
    output is anything that can be set to a float value, though a current output
    is probably most common. After setting the new value of current, this value is checked
    to be within a range around the desired value.

    **NOTE**
    The "exchange" and "keys" arguments list below come from the Service class but
    are not valid for this class. Any value provided will be ignored
    '''

    def __init__(self,
                 payload_field='value_raw',
                 tolerance = 0.01,
                 target_value=0,
                 proportional=0.0, integral=0.0, differential=0.0,
                 maximum_out=15.0, minimum_out=0.0, delta_out_min= 0.001,
                 enable_offset_term=True,
                 minimum_elapsed_time=0,
                 pid_auto_mode=1, # for simple-pid
                 pid_PonM = False,
                 p_term = 0,
                 i_term = 0,
                 d_term = 0,
                 change_to_current = 0,
                 **kwargs
                ):
        '''
        input_channel (str): name of the logging sensor to use as input to PID (this will override any provided values for keys)
        output_channel (str): name of the endpoint to be set() based on PID
        check_channel (str): name of the endpoint to be checked() after a set()
        status_channel (str): name of the endpoint which controls the status of the heater (enabled/disabled output)
        payload_field (str): name of the field in the payload when the sensor logs (default is 'value_cal' and 'value_raw' is the only other expected value)
        target_value (float): numerical value to which the loop will try to lock the input_channel
        proportional (float): coefficient for the P term in the PID equation
        integral (float): coefficient for the I term in the PID equation
        differential (float): coefficient for the D term in the PID equation
        maximum_out (float): max value to which the output_channel may be set; if the PID equation gives a larger value this value is used instead
        delta_out_min (float): minimum value by which to change the output_channel; if the PID equation gives a smaller change, the value is left unchanged (no set is attempted)
        tolerance (float): acceptable difference between the set and get values (default: 0.01)
        minimum_elapsed_time (float): minimum time interval to perform PID calculation over
        '''
        #kwargs.update({'alert_keys':['sensor_value.'+input_channel]})

        #self._set_channel = output_channel
        #self._check_channel = check_channel
        #self._status_channel = status_channel
        self.payload_field = payload_field
        self.tolerance = tolerance

        self._last_data = {'delta':None, 'time':datetime.datetime.utcnow(), 'lastInput':0}
        self.target_value = target_value

        self.Kproportional = proportional
        self.Kintegral = integral
        self.Kdifferential = differential
 
        self.p_term = p_term
        self.i_term = i_term
        self.d_term = d_term
        self.change_to_current = change_to_current
        # save initial values
        self._old_Kp = self.Kproportional
        self._old_Ki = self.Kintegral
        self._old_Kd = self.Kdifferential

 #       self._integral= 0

        self.max_current = maximum_out
        self.min_current = minimum_out
        self.min_current_change = delta_out_min

 #       self.enable_offset_term = enable_offset_term
        self.minimum_elapsed_time = minimum_elapsed_time

        self.pid_auto_mode = pid_auto_mode # for simple-pid
        if self.pid_auto_mode == 1:
            self._old_pid_auto_mode = 1
        elif pid_auto_mode  == 0:
            self._old_pid_auto_mode = 0
        else:
            raise ValueError(f'pid_auto_mode is neither 0 nor 1: {pid_auto_mode}')

        self.__validate_status()
        self._old_current = self.__get_current()
        logger.info('starting current is: {}'.format(self._old_current))

     # create instance of simple-pid
        self.first_run = True
        self.pid = PID(self.Kproportional,
                       self.Kintegral,
                       self.Kdifferential,
                       setpoint = self.target_value)
        self.pid.output_limits = (-0.5,0.5)
        self.pid.proportional_on_measurement = False
        # self.pid.proportional_on_measurement = pid_PonM

        "If set to None, the PID will compute a new output value every time it is called."
        self.pid.sample_time = None

        # self.pid.auto_mode = self.pid_auto_mode

        if self.pid_auto_mode == 1:
            # turn on PID and start at the existing current
            self.pid.set_auto_mode(True, last_output = 0)
        elif self.pid_auto_mode == 0:
            # don't turn on PID
            self.pid.auto_mode = False
        else:
            logger.critical('self.auto_mode value {} is neither true nor false'.format(self.pid_auto_mode))

    def __get_current(self): #TODO: Remove hardcoded broker information
        value = con.get("habs_current_output_dl3")

        try:
            value = float(value)
        except Exception as err: 
            raise ValueError('value get ({}) is not floatable'.format(value))    
        return value

    def __validate_status(self):
        value = con.get("habs_power_status_dl3")

        if value.startswith("ON"):
            logger.debug("{} returns {}".format("habs_power_status",value))
        else:
            logger.critical("Invalid status of {} for PID control by {}".format("habs_power_status",self.name))


    def set_current(self, value):
        logger.info('going to set new current to: {}'.format(value))
        reply = con.set("habs_current_limit_dl3", value)
        logger.info('set response was: {}'.format(reply))

    def read_setpoint_from_file(self):
        with open("pid_setpoint.txt", "r") as f:
            setpoint = float(f.readlines()[0])
        return setpoint

    def write_values_to_file(self):
        values = {
            'habs_current_limit_dl3': con.get("habs_current_limit_dl3"),
            'thermocouple_temp': con.get("read_V_TC_HABS_Source_MATS_dl3"),
            'power_status': con.get("habs_power_status_dl3"),
            'pid_auto_mode': self.pid_auto_mode,
            'pid_setpoint': self.pid.setpoint,
            'change_to_current': self.change_to_current,
            'Kproportional': self.Kproportional,
            'Kintegral': self.Kintegral,
            'Kdifferential': self.Kdifferential,
            'p_term': self.p_term,
            'i_term': self.i_term,
            'd_term': self.d_term,
        }
        with open("pid_temporary_values.json", "w") as f:
            json.dump(values, f)
    
    # This was conjured up by Max and Darius as a way to gain access to the PID coefficients for tuning
    def send_pid_coefficients_to_log(self, *value):
        logger.info(f'PID coefficients: {value[0]:.5f}; {value[1]:.5f}; {value[2]:.5f}')


    def current_from_TC(self, TC):
        '''
        Calcuates the estimated steady-state current for a given TC target value

        Based on data from 2023-02-18T01:01:02Z to 2023-02-18T21:57:52Z
        and TC = 50 point from 2023-03-03T2200Z
 See AGBoeser\Project8\Phase_IV\Lab\Slow_Controls\dataDownloads\2023-02-18T0100.csv
        '''
        if TC > 100:
            # power law approximate fit above TC = 100
            # good to ~ 10 %, maybe?
            A = 500
            power = 0.4
            minus = 750
            adj_current = 0.087098992
            est_current = ((TC+minus)/A)**(1/power) + adj_current
        elif TC > 50:
            # linear interpolation between 50 at 2.662 A and 100 at 3.68 A
            m = 49.11591356
            b = -80.7956778
            est_current = (TC-b)/m
        elif TC > 24.65:
            # linear interpolation between 24.65 at zero current and 50 at 2.662 A
            # this part is unreliable
            m = 9.522915101
            b = 24.65
            est_current = (TC-b)/m
        else:
            logger.info('TC reading should not be <= 24.65; estimating zero current')
            est_current = 0
        logger.info(f'current_from_TC({TC}) returning est_current = {est_current} A')
        return est_current


    # Respond to a new message on the exchange from the sensor endpoint
    # Because this file is a Gogol, the appearance of the message
    # is the trigger for computing a new PID output value
    def on_alert_message(self):

        this_value = self.read_setpoint_from_file()# float(con.get("read_V_TC_HABS_Source_MATS_dl3"))

        # if this is the first run after starting the service
        # and the sensor reading (this_value) is more than 1 [TC unit] different from the target_value
        # change the target value to the present sensor reading
        # and update the PID setpoint to that value as well
        if self.first_run == True:
            logger.info('This is the first run of this_consume')
            if abs(self.target_value - this_value) > 1:
                # change target to present value
                self.target_value = this_value
                # send setpoint to simple-pid
                self.pid.setpoint = self.target_value

        this_time = datetime.datetime.utcnow()
        if (this_time - self._last_data['time']).total_seconds() < self.minimum_elapsed_time:
            # handle self._force_reprocess from @target_value.setter
            if not self._force_reprocess:
                logger.info("not enough time has elasped: {}[{}]".format((this_time - self._last_data['time']).total_seconds(),self.minimum_elapsed_time))
                return
            logger.info("Forcing process due to changed target_value")
            self._force_reprocess = False
        # update all simple-pid params
        #self.pid.setpoint = self.target_value
        logger.info('Setting PID tunings to ({self.Kproportional}, {self.Kintegral}, {self.Kdifferential})')
        self.pid.tunings = (self.Kproportional, self.Kintegral, self.Kdifferential)
        logger.info('simple-pid tunings are {self.pid.tunings}')
        if (self.pid_auto_mode == 1) and (self._old_pid_auto_mode == 0):
            if abs(self.target_value - this_value) > 1:
                # change target to present value
                self.target_value = this_value
                # send setpoint to simple-pid
                self.pid.setpoint = self.target_value
            self.pid.set_auto_mode(True, last_output = 0)
        if self.pid_auto_mode == 0:
            self.pid.auto_mode = False
        #self.pid.proportional_on_measurement = self.pid_PonM
        logger.info(f'Variables outside simple-pid object: self._old_pid_auto_mode {self._old_pid_auto_mode}; self.pid_auto_mode {self.pid_auto_mode}')
        logger.info('Updated simple-pid params: setpoint = {}, tune = {}, pid.auto_mode = {}'.format(self.pid.setpoint, self.pid.tunings, self.pid.auto_mode))
     # mark that the next invocation will not be the first run
        self.first_run = False

        # start process of computing and setting a new output

        self.process_new_value(timestamp=this_time, value=float(this_value))

    # Use the new sensor reading to adjust the output value
    def process_new_value(self, value, timestamp):
        # send auto mode state to database


        # send setpoint to simple-pid
        self.pid.setpoint = self.target_value
        logger.info(f'simple-pid thinks setpoint is {self.pid.setpoint}; requested was {self.target_value}')

        # compute change in time
        dt = (timestamp - self._last_data['time']).total_seconds()

        if dt > 6:
            dt = 6.0

        # check that simple-pid has the right tuning values
        self.pid.tunings = (self.Kproportional, self.Kintegral, self.Kdifferential)
        # assert self.pid.tunings == (self.Kproportional, self.Kintegral, self.Kdifferential)
        if self.pid.tunings[0] != self.Kproportional:
            logger.info(f'simple-pid\'s P value ({self.pid.tunings[0]}) does not match requested P ({self.Kproportional})')
        if self.pid.tunings[1] != self.Kintegral:
            logger.info(f'simple-pid\'s I value ({self.pid.tunings[0]}) does not match requested I ({self.Kintegral})')
        if self.pid.tunings[2] != self.Kdifferential:
            logger.info(f'simple-pid\'s D value ({self.pid.tunings[0]}) does not match requested D ({self.Kdifferential})')

        # Compute new current using simple-pid
        # This will go through checks before being set later on
        logger.info('Computing new output value with simple-pid')
        original_change_to_current = self.pid(float(value))
        #logger.info(f'simple-pid initially requested a new total current of {new_current}')
        self.p_term, self.i_term, self.d_term = self.pid.components
        logger.info('The computed constituents are: p_term = {}, i_term = {}, d_term = {}'.format(self.p_term, self.i_term, self.d_term))
        logger.info(f'Relative to the previous current, simple-pid has requested a change of {original_change_to_current}')

        # compute the difference between the sensor reading and the target
        delta = (value - self.target_value) # this used to be an absolute value
        abs_delta = abs(delta) # TODO: is this redundant?

        # gain-schedule the d_term when close to the setpoint to minimize noise
        try:
            last_abs_delta = abs(self._last_data['delta'])
        except:
            last_abs_delta = 0
        # adjusted so that d_term is cut to 1% of the normal value
        # within a range equal to the noise band we observe when stable at a setpoint
        self.d_term = self.d_term * (1 - (1-0.01) * (1 / (1 + ((delta/0.05)**6))))
        logger.info(f'd_term has been cut to {self.d_term}')

        self.write_values_to_file()

        self.change_to_current = self.p_term + self.i_term + self.d_term

        # reduce the commanded change to B*change_to_current
        # in a narrow region with a half width of 2*B_width
        # around the setpoint
        self.B = 0.02
        self.B_width = 10
        self.B_exp = 2
        if dt > 0:
            if (((abs_delta - last_abs_delta )**2 )**0.5 / dt ) > 1:
                # if the slope of the error (either towards or away from the setpoint)
                # is larger than 1 [TC unit]/[s], apply braking
                braking = 1 - (1-self.B) * (1 / (1 + ((delta/self.B_width)**self.B_exp)))
                self.change_to_current = braking * self.change_to_current
                logger.info(f'Braking reduced output change to {self.change_to_current}')

        # check if change is bigger than minimum change
        # if not, don't set a new current
        # this is the first place the function can return,
        # so need to save values
        if abs(self.change_to_current) < self.min_current_change:
            logger.info("current change less than min delta")
            self.change_to_current = 0
            logger.info("old[change] are: {}[{}]".format(self._old_current, self.change_to_current))
            self._old_pid_auto_mode = self.pid_auto_mode
            self._old_current = self._old_current + self.change_to_current
            self._old_Kp = self.Kproportional
            self._old_Ki = self.Kintegral
            self._old_Kd = self.Kdifferential
            self._last_data['time'] = timestamp
            self._last_data['delta'] = delta
            logger.info("Saved values for next run: self._old_current {}, self._old_Kp {}, self._old_Ki {}, self._old_Kd {}, self._last_data['time'] {}".format(self._old_current, self._old_Kp, self._old_Ki, self._old_Kd, self._last_data['time'] ))
            self.write_values_to_file()
            return


        # To minimize over/undershoot, use a lookup function to get the
        # the estimated steady-state current (ESSC) at the target TC value.
        # When the actual current crosses the ESSC, hold at the ESSC
        # until the error (TC vs SP) is less than some percentage
        # TODO: apply some multiple of the essc until the measured value gets within some outer tolerance, then jump to the essc
        #       That should probably depend on the size of the change in SP
        logger.info(f'Computing est_current with TC = {float(self.target_value)}')
        est_current = self.current_from_TC(float(self.target_value))
        next_new_current = (self._old_current or 0) + self.change_to_current

        # negative if approaching SP from above
        # positive if approaching SP from below
        # dError = delta - self._last_data['delta']
        # negative if approaching SP; positive if moving away
        # abs_dError = abs(dError)
        # if abs_dError < 0:
        #     logger.info(f'The absolute value of the error is shrinking; setting `approaching_target = True`')
        #     approaching_target = True
        # else:
        #     logger.info(f'The absolute value of the error is growing; setting `approaching_target = False`')
        #     approaching_target = False

        if self.target_value > 0:
            rel_error = abs(delta)/self.target_value
        elif self.target_value == 0:
            rel_error = abs(delta)
        else:
            raise ValueError

        if self.target_value > 0:
            if (rel_error >= 0.05) and (rel_error <= 0.2):
                logger.info(f'The relative error is between 5% and 20%; setting `error_in_band = True`')
                error_in_band = True
            else:
                logger.info(f'The relative error is outside 5% to 20%; setting `error_in_band = False`')
                error_in_band = False
        elif self.target_value == 0:
            error_in_band = False
        else:
            raise ValueError

        # if (approaching_target == True) and (self.target_value >= 50) and (error_in_band == False):
        if (self.target_value >= 50) and (error_in_band == True):
            # if measured value is moving towards SP, and
            #    the SP is within the range of the estimation function, and
            #    the error is more than the given percentage
            # then replace the PID current request with the ESSC

            # when old_current is 10 and est_current is 11, change is 1
            # when old_current is 10 and est_current is 9, change is -1
            self.change_to_current = (est_current - self._old_current)
            logger.info(f'TC {value}; Error {delta}; SP {self.target_value}; rel. error {rel_error}; Replacing original change_to_current with {self.change_to_current} A from lookup of ESSC ({est_current} A)')

        else:
            logger.info(f'Conditions for lookup of ESSC not met; continuing with PID change to current of {self.change_to_current}')


        # Limit output ramp rate to X A/min
        ramp_rate_limit_A_per_min = 2/60 #2/60
        if (abs(self.change_to_current / dt)) > ramp_rate_limit_A_per_min:
            sign = 1
            if self.change_to_current < 0:
                sign = -1
            self.change_to_current = ramp_rate_limit_A_per_min * dt * sign
            logger.info(f'Ramp rate limit reduced output change to {self.change_to_current}')

        # Convert adjusted change_to_current back into new total current
        new_current = (self._old_current or 0) + self.change_to_current

        # test if current within allowed parameters
        logger.info('computed new current to be: {}'.format(new_current))
        if new_current > self.max_current:
            logger.info("new current above max")
            # clamp new_current to max
            new_current = self.max_current
        if new_current < self.min_current:
            logger.info("new current below min")
            # clamp new_current to min
            new_current = self.min_current
        if new_current < 0.:
            logger.info("new current < 0")
            # clamp new_current to 0
            new_current = 0.

        # re-compute the resulting change_to_current
        self.change_to_current = new_current - self._old_current
        # log the final current change
        #self.send_change_to_current_to_db(self.change_to_current)
        # send the final, total new_current to the power supply
        if self.pid_auto_mode == 1:
            self.set_current(new_current)
        else:
            logger.info(f'Not setting current because pid_auto_mode != True')
            # save existing current so the storage with `self._old_current = new_current`
            # down below has the corect value for the next iteration
            new_current = self._old_current


        # confirm the power supply is actually putting out the requested value
        logger.debug("allow settling time and checking the current value")
        current_get = self.__get_current()
        if abs(current_get-new_current) < self.tolerance:
            logger.info("current set is equal to current get")
        else:
            self.__validate_status()

        # save the old values for the next loop
        # this is the final place the function can return,
        # so need to save values
        logger.info("current set is: {}".format(new_current))
        self._old_pid_auto_mode = self.pid_auto_mode
        self._old_current = new_current
        self._old_Kp = self.Kproportional
        self._old_Ki = self.Kintegral
        self._old_Kd = self.Kdifferential
        self._last_data['time'] = timestamp
        self._last_data['delta'] = delta
        logger.info("Saved values for next run: self._old_current {}, self._old_Kp {}, self._old_Ki {}, self._old_Kd {}, self._last_data['time'] {}".format(self._old_current, self._old_Kp, self._old_Ki, self._old_Kd, self._last_data['time'] ))
        self.write_values_to_file()



