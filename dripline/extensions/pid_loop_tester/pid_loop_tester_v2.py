"""
Implementation of a PID loop tester for the Dripline framework.
This module provides a service that can be used to test PID control loops by simulating
the behavior of a system of heaters and sensors.

Thermal plant (1-R-1-C):
    C dT/dt = P_heater(t) - (T - T_env)/R_th + D(t)

Throttle mapping:
    - throttle_mode="current": P = eta * R_heater * clamp(I,0,I_max)^2
    - throttle_mode="power"  : P = clamp(P,0,P_max)
"""
from __future__ import print_function
__all__ = []

from dripline.core import Service, ThrowReply
import math
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from time import sleep
 
__all__.append('PidLoopTester')

class PidLoopTester(Service):
    '''
    A service that simulates hardware endpoints for testing PID control loops.
    Uses KeyValueStore to manage states.

    Endpoints:
        - throttle_endpoint: controller writes throttle (current [A] or power [W])
        - sensor_endpoint  : tester writes simulated sensor temperature [K]
    '''

    def __init__(self,
                 # ---- Simulation timing ----
                 time_step=0.1,
                 time=0.0,

                 # ---- Initial condition ----
                 T0=40.0,                # initial sensor temperature [K]

                 # ---- Thermal model (1R1C) ----
                 C=10.0,                 # heat capacity [J/K]
                 R_th=1.0,               # thermal resistance to bath [K/W]
                 T_env=40.0,             # bath/ambient temperature [K]

                 # ---- Actuator/throttle mapping ----
                 I_0=0.0,                 # initial current [A]
                 throttle_mode='current',# 'current' (A) or 'power' (W)
                 I_max=2.5,              # A, clamp for current mode
                 R_heater=6.0,           # ohms, for current mode power = eta * R_heater * I^2
                 eta=0.95,               # efficiency into modeled node(s)
                 P_max=100.0,            # W, clamp for power mode (ignored in current mode)

                 # ---- I/O plumbing ----
                 read_field='value_cal',
                 throttle_endpoint=None,
                 sensor_endpoint=None,

                 # ---- Extras ----
                 enable_disturbance=True,

                 **kwargs
                ):
        '''
        Args:
            time_step (float): integration step [s]
            T0 (float): initial sensor temperature [K]
            C (float): heat capacity [J/K]
            R_th (float): thermal resistance to bath [K/W]
            T_env (float): bath temperature [K]
            throttle_mode (str): 'current' or 'power'
            I_max (float): current clamp [A]
            R_heater (float): heater resistance [ohm]
            eta (float): electrical->thermal efficiency (0..1)
            P_max (float): power clamp [W] for power mode
            read_field (str): field name stored in KVS dicts
            throttle_endpoint (str): KVS key for throttle
            sensor_endpoint (str): KVS key for sensor
            enable_disturbance (bool): toggle external disturbance term
        '''
        Service.__init__(self, **kwargs)

        # Timing / state
        self._dt = float(time_step)
        self._time = float(time)

        # Plant params
        self._C = float(C)
        self._Rth = float(R_th)
        self._Tenv = float(T_env)

        # Actuator map
        self._mode = str(throttle_mode).lower()
        self._Imax = float(I_max)
        self._Rheater = float(R_heater)
        self._eta = float(eta)
        self._Pmax = float(P_max)

        # I/O
        self._read_field = read_field
        self._throttle_endpoint = throttle_endpoint
        self._sensor_endpoint = sensor_endpoint

        # Disturbance toggle
        self._enable_disturbance = bool(enable_disturbance)

        # Initialize endpoints
        if self._sensor_endpoint is None or self._throttle_endpoint is None:
            raise ThrowReply("Both sensor_endpoint and throttle_endpoint must be configured")

        self.set_sensor_value(T0)      # temperature [K]
        # Initialize throttle to 0 (safe)
        self.set_throttle_value(I_0)

        # Main loop
        while True:
            self.time_step()
            sleep(self._dt)

    # ------------------ KVS helpers ------------------

    def get_sensor_value(self):
        '''
        Get temperature [K] from sensor endpoint.
        '''
        if self._sensor_endpoint is None:
            raise ThrowReply("No sensor endpoint configured")
        return self.get(self._sensor_endpoint)[self._read_field]
    
    def set_sensor_value(self, value):
        '''
        Set temperature [K] to sensor endpoint.
        '''
        if self._sensor_endpoint is None:
            raise ThrowReply("No sensor endpoint configured")
        self.set(self._sensor_endpoint, value)
        self._Tenv = value

    def get_throttle_value(self):
        '''
        Get throttle from throttle endpoint (A in 'current' mode, W in 'power' mode).
        '''
        if self._throttle_endpoint is None:
            raise ThrowReply("No throttle endpoint configured")
        return self.get(self._throttle_endpoint)[self._read_field]
    
    def set_throttle_value(self, value):
        '''
        Set throttle to throttle endpoint.
        '''
        if self._throttle_endpoint is None:
            raise ThrowReply("No throttle endpoint configured")
        self.set(self._throttle_endpoint, value)

    # ------------------ Disturbance model ------------------

    def external_disturbance(self, t):
        '''
        External disturbance power D(t) [W]. Positive -> heating, negative -> cooling.
        Feel free to customize.
        '''
        if not self._enable_disturbance:
            return 0.0

        if 10.0 < t < 15.0:
            return -1.0   # brief cooling event
        elif 20.0 < t < 25.0:
            return +0.5   # brief heating event
        elif t > 40.0:
            return 0.2 * math.sin(t)  # slow oscillating background
        else:
            return 0.0

    # ------------------ Actuator mapping ------------------

    def _power_from_throttle(self, throttle_value):
        '''
        Map throttle to heater power [W].
        - current mode: throttle=I[A] -> P=eta*R_heater*I^2
        - power   mode: throttle=P[W] (clamped)
        '''
        if self._mode == 'current':
            I = max(0.0, min(self._Imax, float(throttle_value)))
            return self._eta * self._Rheater * (I ** 2)
        elif self._mode == 'power':
            return max(0.0, min(self._Pmax, float(throttle_value)))
        else:
            raise ThrowReply("throttle_mode must be 'current' or 'power'")

    # ------------------ Simulation step ------------------

    def time_step(self):
        '''
        Advance the thermal plant by dt using forward Euler.
        C dT/dt = P_heater - (T - T_env)/R_th + D(t)
        '''
        # Read current state and command with error handling
        try:
            T = float(self.get_sensor_value())           # [K]
            throttle = float(self.get_throttle_value())  # [A] or [W] depending on mode
        except Exception as e:
            logger.warning(f"Failed to read endpoints, using default values: {e}")
            T = self._Tenv  # Use ambient temperature as fallback
            throttle = 0.0  # Use zero throttle as fallback
        
        # Heater power (W)
        P_heater = self._power_from_throttle(throttle)

        # Heat loss to bath (positive when T > T_env)
        P_loss = (T - self._Tenv) / self._Rth       # [W]

        # External disturbance (W)
        D = self.external_disturbance(self._time)

        # Integrate temperature
        dT_dt = (P_heater - P_loss + D) / self._C
        T_new = T + self._dt * dT_dt

        # Write back & log
        self.set_sensor_value(T_new)
        logger.info(
            f'FROM TESTER: t={self._time:.2f}s, T={T_new:.3f} K, '
            f'throttle={throttle:.4f} ({self._mode}), P={P_heater:.3f} W, D={D:.3f} W'
        )

        # Advance sim time
        self._time += self._dt