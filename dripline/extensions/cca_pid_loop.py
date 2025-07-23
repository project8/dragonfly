'''
Implementation of a PID control loop
'''

from __future__ import print_function
__all__ = []

import time
import datetime
import simple_PID
import PID
from dripline.core import AlertConsumer
from dripline.core import Interface
from dripline.core import ThrowReply 

import logging
logger = logging.getLogger(__name__)

__all__.append('PidController')
class PidController(AlertConsumer):
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
                 input_channel,
                 output_channel,
                 check_channel,
                 status_channel,
                 payload_field='value_cal',
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
        kwargs.update({'alert_keys':['sensor_value.'+input_channel]})
        AlertConsumer.__init__(self, **kwargs)

        self._set_channel = output_channel
        self._check_channel = check_channel
        self._status_channel = status_channel
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
        self.__validate_status()
        self._old_current = self.__get_current()
        logger.info('starting current is: {}'.format(self._old_current))

    def __get_current(self):
        connection={
            "broker": "rabbit-broker",
            "auth-file": "/root/authentications.json"
        }

        con = Interface(connection)
        value = con.get(self._check_channel).payload[self.payload_field].as_string()

        logger.info('old current is {}'.format(value))


        try:
            value = float(value)
            
        except Exception as err: ##TODO correct exceptions
            raise ThrowReply('value get ({}) is not floatable'.format(value))    
        return value


  # dripline utilities

    @property
    def target_value(self):
        return self._target_value
    @target_value.setter
    def target_value(self, value):
        self._target_value = value
        self._integral = 0
        self._force_reprocess = True

    @property
    def pid_auto_mode(self):
        return self._pid_auto_mode
    @pid_auto_mode.setter
    def pid_auto_mode(self, value):
        self._pid_auto_mode = value
        #self._force_reprocess = True

    @property
    def Kproportional(self):
        return self._Kproportional
    @Kproportional.setter
    def Kproportional(self, value):
        self._Kproportional = value

    @property
    def Kintegral(self):
        return self._Kintegral
    @Kintegral.setter
    def Kintegral(self, value):
        self._Kintegral = value

    @property
    def Kdifferential(self):
        return self._Kdifferential
    @Kdifferential.setter
    def Kdifferential(self, value):
        self._Kdifferential = value

    @property
    def p_term(self):
        return self._p_term
    @p_term.setter
    def p_term(self, value):
        self._p_term = value

    @property
    def i_term(self):
        return self._i_term
    @i_term.setter
    def i_term(self, value):
        self._i_term = value

    @property
    def d_term(self):
        return self._d_term
    @d_term.setter
    def d_term(self, value):
        self._d_term = value

    @property
    def change_to_current(self):
        return self._change_to_current
    @change_to_current.setter
    def change_to_current(self, value):
        self._change_to_current = value

    def set_current(self, value):
        logger.info('going to set new current to: {}'.format(value))
        reply = self.service.set(self._set_channel, value)
        logger.info('set response was: {}'.format(reply))

    # These functions broadcast their values to the dripline exchange in
    # a way that allows those values to go into the database without locking
    # up the pid_loop thread by trying to send and recieve the same message
    # at the same time.
    def send_p_term_to_db(self, value):
        logger.info('going to send new p_term to DB: {}'.format(value))
        values = {'value_raw': value, 'value_cal': value}
        #reply = self.store_value(alert=values, severity='sensor_value.p_term')
        logger.info('set response was: {}'.format(reply))

    def send_i_term_to_db(self, value):
        logger.info('going to send new i_term to DB: {}'.format(value))
        values = {'value_raw': value, 'value_cal': value}
        #reply = self.store_value(alert=values, severity='sensor_value.i_term')
        logger.info('set response was: {}'.format(reply))

    def send_d_term_to_db(self, value):
        logger.info('going to send new d_term to DB: {}'.format(value))
        values = {'value_raw': value, 'value_cal': value}
        #reply = self.store_value(alert=values, severity='sensor_value.d_term')
        logger.info('set response was: {}'.format(reply))

    def send_change_to_current_to_db(self, value):
        logger.info('going to send new change_to_current to DB: {}'.format(value))
        values = {'value_raw': value, 'value_cal': value}
        #reply = self.store_value(alert=values, severity='sensor_value.change_to_current')
        logger.info('set response was: {}'.format(reply))

    def send_pid_auto_mode_to_db(self, value):
        logger.info('going to send new pid_auto_mode to DB: {}'.format(value))
        values = {'value_raw': value, 'value_cal': value}
        #reply = self.store_value(alert=values, severity='sensor_value.pid_auto_mode')
        logger.info('set response was: {}'.format(reply))

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


    def __validate_status(self):
        connection={
            "broker": "rabbit-broker",
            "auth-file": "/root/authentications.json"
        }

        con = Interface(connection)

        value = con.get(self._status_channel).payload["value_raw"].as_string()

        logger.info("{} returns {}".format(self._status_channel,value))
        if value == "ON":
            logger.debug("{} returns {}".format(self._status_channel,value))
        else:
            logger.critical("Invalid status of {} for PID control by {}".format(self._status_channel,self.name))
       #     raise ThrowReply("{} returns {}".format(self._status_channel,value))

    def on_alert_message(self, message):
        logger.info('consuming message {}'.format(message))
        this_value = message.payload[self.payload_field].as_double()
        if this_value is None:
            logger.info('value is None')
            return



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



        this_time = datetime.datetime.strptime(message.timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
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

    @property
    def target_value(self):
        return self._target_value
    @target_value.setter
    def target_value(self, value):
        self._target_value = value
        self._integral = 0
        self._force_reprocess = True

    def set_current(self, value):
        connection={
            "broker": "rabbit-broker",
            "auth-file": "/root/authentications.json"
        }

        con = Interface(connection)
        logger.info('going to set new current to: {}'.format(value))
        reply = con.set(self._set_channel, value)
        logger.info('set response was: {}'.format(reply))
    # Use the new sensor reading to adjust the output value


    # Use the new sensor reading to adjust the output value
    def process_new_value(self, value, timestamp):

        # send auto mode state to database
        self.send_pid_auto_mode_to_db(self.pid_auto_mode)

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

        # send initial values to database for slowplot
        self.send_p_term_to_db(self.p_term)
        self.send_i_term_to_db(self.i_term)
        self.send_d_term_to_db(self.d_term)
        logger.info('Logged requested p, i, and d_terms')

        # just to be sure
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
            self.send_change_to_current_to_db(0)
            self._old_pid_auto_mode = self.pid_auto_mode
            self._old_current = self._old_current + self.change_to_current
            self._old_Kp = self.Kproportional
            self._old_Ki = self.Kintegral
            self._old_Kd = self.Kdifferential
            self._last_data['time'] = timestamp
            self._last_data['delta'] = delta
            logger.info("Saved values for next run: self._old_current {}, self._old_Kp {}, self._old_Ki {}, self._old_Kd {}, self._last_data['time'] {}".format(self._old_current, self._old_Kp, self._old_Ki, self._old_Kd, self._last_data['time'] ))
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
        self.send_change_to_current_to_db(self.change_to_current)
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
            # actual current is not within the acceptable range around the requested value
            self.__validate_status()
            # Record values and throw an exception
            # this is the second place the function can return,
            # so need to save values
            self._old_pid_auto_mode = self.pid_auto_mode
            self._old_current = new_current
            self._old_Kp = self.Kproportional
            self._old_Ki = self.Kintegral
            self._old_Kd = self.Kdifferential
            self._last_data['time'] = timestamp
            self._last_data['delta'] = delta
            logger.info("Saved values for next run: self._old_current {}, self._old_Kp {}, self._old_Ki {}, self._old_Kd {}, self._last_data['time'] {}".format(self._old_current, self._old_Kp, self._old_Ki, self._old_Kd, self._last_data['time'] ))
#            raise exceptions.DriplineValueError("set value ({}) is not equal to checked value ({})".format(new_current,current_get))

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


'''
#OldVersion
    def process_new_value(self, value, timestamp):

        delta = self.target_value - value
        logger.info('value is <{}>; delta is <{}>'.format(value, delta))

        self._integral += delta * (timestamp - self._last_data['time']).total_seconds()
        if (timestamp - self._last_data['time']).total_seconds() < 2*self.minimum_elapsed_time:
            try:
                derivative = (self._last_data['value'] - value) / (timestamp - self._last_data['time']).total_seconds()
            except TypeError:
                derivative = 0
        else:
            logger.warning("invalid time for calculating derivative")
            derivative = 0.
        self._last_data = {'value': value, 'time': timestamp}

        logger.info("proportional <{}>; integral <{}>; differential <{}>".format\
            (self.Kproportional*delta, self.Kintegral*self._integral, self.Kdifferential*derivative))
        change_to_current = (self.Kproportional * delta +
                             self.Kintegral * self._integral +
                             self.Kdifferential * derivative
                            )
        new_current = (self._old_current or 0)*self.enable_offset_term + change_to_current

        if abs(change_to_current) < self.min_current_change:
            logger.info("current change less than min delta")
            logger.info("old[new] are: {}[{}]".format(self._old_current,new_current))
            return
        logger.info('computed new current to be: {}'.format(new_current))
        if new_current > self.max_current:
            logger.info("new current above max")
            new_current = self.max_current
        if new_current < self.min_current:
            logger.info("new current below min")
            new_current = self.min_current
        if new_current < 0.:
            logger.info("new current < 0")
            new_current = 0.

        self.set_current(new_current)
        logger.debug("allow settling time and checking the current value")
        # FIXME: remove sleep when set_and_check handled properly
        time.sleep(1)
        current_get = self.__get_current()
        if abs(current_get-new_current) < self.tolerance:
            logger.debug("current set is equal to current get")
        else:
            self.__validate_status()
            raise ThrowReply("set value ({}) is not equal to checked value ({})".format(new_current,current_get))

        logger.info("current set is: {}".format(new_current))
        self._old_current = new_current
'''
