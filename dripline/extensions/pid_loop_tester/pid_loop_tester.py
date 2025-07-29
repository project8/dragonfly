'''
Implementation of a PID loop tester for the Dripline framework.
This module provides a service that can be used to test PID control loops by simulating
the behavior of a system of heaters and sensors.
'''
from __future__ import print_function
__all__ = []

from dripline.core import Service, ThrowReply

import logging
logger = logging.getLogger(__name__)

from time import sleep
 
__all__.append('PidLoopTester')

class PidLoopTester(Service):
    '''
    A service that simulates hardware and endpoints for testing PID control loops.
    Uses KeyValueStore to manage states, just using a velocity regulation example Ali posted in the slack. 
    '''

    def __init__(self,
                 drag=0.1,
                 time_step=0.1,
                 time=0.0,
                 throttle_endpoint=None,
                 sensor_endpoint=None,
                 **kwargs
                ):
        '''
        T0 (float): 
        '''
        Service.__init__(self, **kwargs)

        self._drag = drag
        self._throttle_endpoint = throttle_endpoint
        self._sensor_endpoint = sensor_endpoint
        self._time_step = time_step
        self._time = time

        while True:
            self.time_step()
            sleep(self._time_step)


    def get_sensor_value(self):
        '''
        Get value from sensor endpoint. 
        '''
        if self._sensor_endpoint is None:
            raise ThrowReply("No sensor endpoint configured")
        return self.get(self._sensor_endpoint)
    
    def set_sensor_value(self, value):
        '''
        Set value to sensor endpoint.
        '''
        if self._sensor_endpoint is None:
            raise ThrowReply("No sensor endpoint configured")
        self.set(self._sensor_endpoint, value)

    def get_throttle_value(self):
        '''
        Get value from throttle endpoint.
        '''
        if self._throttle_endpoint is None:
            raise ThrowReply("No throttle endpoint configured")
        return self.get(self._throttle_endpoint)
    
    def set_throttle_value(self, value):
        '''
        Set value to throttle endpoint.
        '''
        if self._throttle_endpoint is None:
            raise ThrowReply("No throttle endpoint configured")
        self.set(self._throttle_endpoint, value)

    def external_disturbance(self, t):
        '''
        Simulate an external disturbance to the system.
        
        Args:
            t (float): Time at which the disturbance occurs.
        '''
        # Example disturbance logic, can be customized
        if t > 20.0:
            disturbance = .5
        else:
            disturbance = 0.0
        return disturbance

    def time_step(self):
        '''
        Simulate a time step in the PID loop.
        
        Args:
            dt (float): Time step duration.
        '''
        # Simulate the system behavior based on the PID parameters and current state
        v = self.get_sensor_value()
        a_throttle = self.get_throttle_value()

        # Update the sensor value based on the heater value and system parameters
        new_v = a_throttle + self._drag * v + self.external_disturbance(self._time)
        
        self.set_sensor_value(new_v)
        self._time += self._time_step
