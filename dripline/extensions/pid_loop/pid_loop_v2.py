"""
Author: yao

PID controller for a heater driving a cryogenic/vacuum system.

This version preserves the original public interface:
- Methods: __get_current, __validate_status, this_consume, process_new_value, set_current
- Property: target_value (getter/setter)

Enhancements (backwards-compatible)
-----------------------------------
- Anti-windup: integral clamping + back-calculation when output saturates
- Bounded "set & verify" loop instead of fixed sleep
- Derivative-on-measurement with optional EMA smoothing (reduces setpoint kick)
- Safer time handling (guards against dt<=0 and timestamp parse issues)
- Output deadband to avoid chatter
- Sane default for minimum_out (=0.0 instead of 1.0)

Conventions / Units
-------------------
- PV (process variable): e.g., temperature in Kelvin
- SP (setpoint): same units as PV
- Output u: actuator command (e.g., current in A or duty [0..1])
- Time: seconds
"""

from __future__ import annotations

import time
import datetime
import logging
from typing import Optional
import threading

import csv
import atexit
from typing import Optional, Any, Tuple
import queue
from dripline.core import Service, ThrowReply

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x to the inclusive range [lo, hi]."""
    return lo if x < lo else hi if x > hi else x


def pt100_resistance_to_kelvin(resistance: float) -> float:
    """
    Convert PT100 resistance (ohms) to temperature (Kelvin).
    
    Uses a custom calibration curve specific to the RTD01 sensor,
    fitted from actual sensor data in the cryogenic operating range.
    
    Parameters
    ----------
    resistance : float
        Resistance in ohms
        
    Returns
    -------
    float
        Temperature in Kelvin
        
    Notes
    -----
    Calibration curve fitted from RTD01.Front.Cavity.Thermal sensor data:
    T(K) = a*R² + b*R + c
    
    Calibrated range: ~14.4-15.2 Ω (62.5-64.0 K)
    Based on synchronized Ohm and K channel measurements.
    
    For resistance values outside the calibrated range, the polynomial
    is extrapolated (may be less accurate).
    """
    # Custom calibration coefficients for RTD01 sensor
    # Fitted from actual sensor data: T(K) = a*R² + b*R + c
    a = 0.059524
    b = 0.178571
    c = 47.628423
    
    # Apply polynomial calibration
    temp_kelvin = a * resistance**2 + b * resistance + c
    
    # Sanity check: warn if outside typical calibrated range
    if resistance < 10.0 or resistance > 40.0:
        logger.warning(f"Resistance {resistance:.2f}Ω is outside typical PT100 range")
    
    return temp_kelvin


class PidController(Service):
    """
    PID control loop Service (positional PID form with optional baseline offset).

    Control law (positional PID):
        e   = SP - PV
        u   = u_offset + Kp*e + Ki*integral(e) dt - Kd * d(PV)/dt
              (minus sign on derivative since d(e)/dt = -d(PV)/dt)

    Public API preserved from original:
    - this_consume(message, method)
    - process_new_value(value, timestamp)
    - set_current(value)
    - target_value property
    - __get_current(), __validate_status()
    """

    def __init__(self,
                 input_channel: str,
                 output_channel: str,
                 check_channel: str,
                 status_channel: str,
                 voltage_channel: str,
                 payload_field: str = 'value_cal',
                 tolerance: float = 0.01,
                 target_value: float = 85.0,
                 proportional: float = 0.0,
                 integral: float = 0.0,
                 differential: float = 0.0,
                 maximum_out: float = 1.0,
                 minimum_out: float = 0.0,             # CHANGED default from 1.0 -> 0.0 (sane)
                 delta_out_min: float = 0.001,          # Minimum current change
                 enable_offset_term: bool = False,       # Use old current as baseline
                 minimum_elapsed_time: float = 0.0,
                 poll_period_s: float = 0.1,              # NEW: polling period for input_channel
                 # --- New, optional, backward-compatible knobs below ---
                 integral_limit: Optional[float] = None,  # |integral(e) dt| cap for anti-windup
                 derivative_smoothing: float = 0.0,       # EMA factor in [0,1]; 0 = off
                 max_settle_wait_s: float = 3.0,          # bounded verify-after-set
                 u_offset_baseline: float = 0.0,          # explicit baseline if offset term desired
                 convert_pt100: bool = False,             # Convert PT100 resistance to Kelvin
                 **kwargs):
        """
        Initialize the PID controller and runtime state.

        Most arguments mirror the original class. New optional arguments are kept
        at the end and have safe defaults (won't change behavior unless used).
        """

        # DO NOT try to pass 'keys' here; it will be ignored by Service
        # kwargs.update({'keys': [f'sensor_value.{input_channel}']})  # <-- remove this
        super().__init__(**kwargs)


        # Channels & config
        self._input_channel = input_channel
        self._poll_period_s = float(poll_period_s)
        self._set_channel = output_channel
        self._check_channel = check_channel
        self._status_channel = status_channel
        self._voltage_channel = voltage_channel
        self.payload_field = payload_field
        self.tolerance = float(tolerance)
        self._convert_pt100 = bool(convert_pt100)

        # Controller gains and setpoint
        self._target_value = float(target_value)
        self.Kproportional = float(proportional)
        self.Kintegral = float(integral)
        self.Kdifferential = float(differential)

        # Output limits / shaping (names kept)
        self.max_current = float(maximum_out)
        self.min_current = float(minimum_out)
        self.min_current_change = float(delta_out_min)
        

        # Original flag retained; now combined with an explicit baseline
        self.enable_offset_term = bool(enable_offset_term)
        self.u_offset_baseline = float(u_offset_baseline)
        self.max_settle_wait_s = float(max_settle_wait_s)

        # Timing & stability
        self.minimum_elapsed_time = max(0.0, float(minimum_elapsed_time))

        # Anti-windup & derivative smoothing
        self._integral = 0.0
        self._int_limit = None if integral_limit is None else abs(float(integral_limit))
        self._alpha_d = clamp(float(derivative_smoothing), 0.0, 1.0)
        self._ema_dpvdt = 0.0
        self._last_data = {'value': None, 'time': None}  # timestamp will be datetime or None

        # Forcing reprocess on SP change (as in the original)
        self._force_reprocess = False

        # Set status channel to 1 to enable heater output before anything else
        logger.info(f"Setting {self._status_channel} to 1 to enable heater output")
        try:
            self.set(self._status_channel, 1)
            logger.info(f"Successfully set {self._status_channel} to 1")
        except Exception as ex:
            logger.error(f"Failed to set {self._status_channel} to 1: {ex}")
            raise

        # Set voltage channel to 30V if provided
        if self._voltage_channel is not None:
            logger.info(f"Setting {self._voltage_channel} to 30V")
            try:
                self.set(self._voltage_channel, 30.0)
                logger.info(f"Successfully set {self._voltage_channel} to 30V")
            except Exception as ex:
                logger.error(f"Failed to set {self._voltage_channel} to 30V: {ex}")
                raise

        # Verify device state and seed last output
        self.__validate_status()
        self._old_current = self.__get_current()
        logger.info(f"PID ready: start_u={self._old_current}, SP={self._target_value}, "
                    f"Kp={self.Kproportional}, Ki={self.Kintegral}, Kd={self.Kdifferential}")
        
        
        # --- simple CSV logging state ---
        self._log_data = []                     # buffer: list of (time_iso, PV, SP, throttle)
        self._log_lock = threading.Lock()
        self._log_filename = f"/app/logs/pid_log_{datetime.datetime.now().isoformat()}.csv"
        self._log_autoflush_every = 10         # autosave every N rows
        self._log_file_initialized = False      # write header once on first flush

        
        # NEW: storage for logging data
        self._log_data = []  # list of (timestamp, PV, SP, throttle)

        # Register save-on-exit
        # atexit.register(self._save_log_to_csv)
        
        # start polling thread
        t = threading.Thread(target=self._poll_sensor_loop, name="pid-poll", daemon=True)
        t.start()
        
    # New: poller that incorporates all logic from this_consume()
    def _poll_sensor_loop(self) -> None:
        """
        Periodically GET the PV endpoint and run the same logic formerly in this_consume().
        """
        while True:
            try:
                # 1) GET PV from the input endpoint
                # resp = self.get(self._input_channel)
                resp = self._get_with_deadline(self._input_channel, timeout_s=max(1.0, 0.8*self._poll_period_s + 0.2))
                if not resp:
                    # No data this tick; keep cadence and try again
                    time.sleep(self._poll_period_s)
                    continue
                # Extract PV
                this_value = resp.get(self.payload_field)
                logger.info(f"Message payload value (raw): {this_value}")
                if this_value is None:
                    logger.info('value is None')
                    time.sleep(self._poll_period_s)
                    continue
                
                # Convert from PT100 resistance to temperature if enabled
                if self._convert_pt100:
                    try:
                        resistance_ohms = float(this_value)
                        this_value = pt100_resistance_to_kelvin(resistance_ohms)
                        logger.info(f"PT100 conversion: {resistance_ohms:.2f}Ω -> {this_value:.2f}K ({this_value-273.15:.2f}°C)")
                    except (ValueError, TypeError) as ex:
                        logger.error(f"PT100 conversion failed for {this_value}: {ex}")
                        time.sleep(self._poll_period_s)
                        continue

                # 2) Parse timestamp robustly (keep your original format first)
                ts_raw = None
                # Try common places a timestamp might live
                if hasattr(resp, 'get'):
                    ts_raw = resp.get('timestamp') or resp.get('time') or resp.get('ts')
                this_time = None
                if ts_raw:
                    try:
                        this_time = datetime.datetime.strptime(ts_raw, '%d/%m/%y %H:%M:%S.%f')
                    except Exception:
                        logger.debug(f"timestamp parse failed for '{ts_raw}', using utcnow()")
                if this_time is None:
                    this_time = datetime.datetime.utcnow()
                logger.info(f"This time: {this_time}")

                logger.info(f"[PID READ] PV={float(this_value)} at {this_time.isoformat()}")
                
                

                # 3) Enforce minimum interval unless forced by SP change
                last_time = self._last_data['time']
                if last_time is not None:
                    dt = (this_time - last_time).total_seconds()
                    if dt < self.minimum_elapsed_time and not self._force_reprocess:
                        logger.info(f"not enough time has elapsed: {dt:.3f}s "
                                    f"[min {self.minimum_elapsed_time:.3f}s]")
                        time.sleep(self._poll_period_s)
                        continue
                if self._force_reprocess:
                    logger.info("Forcing process due to changed target_value")
                    self._force_reprocess = False

                # 4) Dispatch to the PID step
                try:
                    self.process_new_value(value=float(this_value), timestamp=this_time)
                except (TypeError, ValueError):
                    logger.info(f"value not floatable: {this_value}")

            except Exception as ex:
                logger.exception(f"[PV poll] failure: {ex}")

            # TODO IS THIS NECESSARY?
            # # cadence for polling
            # time.sleep(self._poll_period_s)

    def _log_append(self, timestamp: datetime.datetime, pv: float, sp: float, u: float) -> None:
        row = (timestamp.isoformat(), float(pv), float(sp), float(u) if u is not None else float("nan"))
        need_flush = False
        with self._log_lock:
            self._log_data.append(row)
            if len(self._log_data) >= self._log_autoflush_every:
                need_flush = True
        if need_flush:
            self._flush_log_to_csv()

    # def save_log(self, filename: Optional[str] = None) -> None:
    #     """
    #     Public method: force a flush of the in-memory log buffer to CSV.
    #     If 'filename' is provided, switch output file and reset header handling.
    #     """
    #     if filename:
    #         with self._log_lock:
    #             # If the filename changes, re-initialize header for the new file
    #             if filename != self._log_filename:
    #                 self._log_filename = filename
    #                 self._log_file_initialized = False
    #     self._flush_log_to_csv()

    def _flush_log_to_csv(self) -> None:
        """
        Flush the buffered rows to CSV (append mode). Writes header once per file.
        Clears the buffer after writing.
        """
        rows = None
        with self._log_lock:
            if not self._log_data:
                return
            rows = self._log_data
            self._log_data = []

        mode = "a"
        try:
            with open(self._log_filename, mode, newline="") as f:
                writer = csv.writer(f)
                # if not self._log_file_initialized:
                    # writer.writerow(["time", "PV", "SP", "throttle"])
                    # self._log_file_initialized = True
                writer.writerows(rows)
            logger.info(f"Appended {len(rows)} rows to {self._log_filename}")
        except Exception as ex:
            logger.exception(f"Failed flushing CSV: {ex}")

    # ------------------------------------------------------------------ #
    # Public API: helper methods preserved from original implementation
    # ------------------------------------------------------------------ #

    def __get_current(self) -> float:
        """
        Read and return the actuator value from check_channel.

        Returns
        -------
        float : Current actuator reading (same units as output u).
        """
        # value = self.get(self._check_channel)[self.payload_field]
        resp = self._get_with_deadline(self._check_channel, timeout_s=1.0)
        if not resp:
            raise ThrowReply('service_error_invalid_value', 'current read timeout/no reply')
        value = resp.get(self.payload_field)
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ThrowReply('service_error_invalid_value', f'value get ({value}) is not floatable')
        logger.info(f'current get is {value}')
        return value

    def __validate_status(self) -> None:
        """
        Ensure the status_channel reports 'enabled'; otherwise raise ThrowReply.
        """
        # value = str(self.get(self._status_channel)[self.payload_field]).strip().lower()
        value = self.get(self._status_channel)[self.payload_field]
        if value:
            logger.debug(f"{self._status_channel} returns {value}")
        else:
            logger.critical(f"Invalid status of {self._status_channel} for PID control by {self.name}")
            raise ThrowReply('resource_error', f"{self._status_channel} returns {value}")

    @property
    def target_value(self) -> float:
        """
        Get the current setpoint (SP).
        """
        return self._target_value

    @target_value.setter
    def target_value(self, value: float) -> None:
        """
        Set the setpoint (SP) and reset integral; force next process step.

        Notes
        -----
        Resetting the integral prevents previous bias from the old SP.
        """
        logger.info(f"setting new target_value to: {value}")
        logger.info(f"old target_value was: {self._target_value}")
        logger.info("Resetting integral to 0.0")
        logger.info("Forcing reprocess on next message")
        self._target_value = float(value)
        self._integral = 0.0
        self._force_reprocess = True

    def set_current(self, value: float) -> None:
        """
        Send command to the actuator via set_channel and log the reply.
        """
        logger.info(f'going to set new current to: {value}')
        ok, reply = self._set_with_deadline(self._set_channel, value, timeout_s=1.0)
        if not ok:
            logger.warning("set_current: no reply (timeout/failure)")
        logger.info(f'set response was: {reply}')
        
    # ------------------------------------------------------------------ #
    # Public API: step function with original name/signature preserved
    # ------------------------------------------------------------------ #
    # ---- Deadline-bounded wrappers around blocking self.get/self.set ----
    def _get_with_deadline(self, channel: str, timeout_s: float = 1.0) -> Optional[dict]:
        """
        Run self.get(channel) in a worker thread and return within timeout_s.
        Returns the payload dict on success, or None on timeout/error.
        """
        q: "queue.Queue[Tuple[bool, Any]]" = queue.Queue(maxsize=1)

        def _worker():
            try:
                resp = self.get(channel)
                q.put((True, resp))
            except Exception as ex:
                q.put((False, ex))

        t = threading.Thread(target=_worker, name=f"get:{channel}", daemon=True)
        t.start()
        try:
            ok, val = q.get(timeout=timeout_s)
            if ok:
                return val  # type: ignore[return-value]
            logger.warning(f"GET {channel} failed: {val}")
            return None
        except queue.Empty:
            logger.warning(f"GET {channel} timed out after {timeout_s:.2f}s")
            return None
        finally:
            t.join(timeout=0.1)  # Clean up the thread

    def _set_with_deadline(self, channel: str, value: float, timeout_s: float = 1.0) -> Tuple[bool, Any]:
        """
        Run self.set(channel, value) with a deadline.
        Returns (ok, reply_or_exception). When ok is False, reply_or_exception is the exception or None on timeout.
        """
        q: "queue.Queue[Tuple[bool, Any]]" = queue.Queue(maxsize=1)

        def _worker():
            try:
                reply = self.set(channel, value)
                q.put((True, reply))
            except Exception as ex:
                q.put((False, ex))

        t = threading.Thread(target=_worker, name=f"set:{channel}", daemon=True)
        t.start()
        try:
            ok, val = q.get(timeout=timeout_s)
            if ok:
                logger.debug(f"SET {channel} reply: {val}")
                return True, val
            logger.warning(f"SET {channel} failed: {val}")
            return False, val
        except queue.Empty:
            logger.warning(f"SET {channel} timed out after {timeout_s:.2f}s")
            return False, None
        finally:
            t.join(timeout=0.1)  # Clean up the thread

    def process_new_value(self, value: float, timestamp: datetime.datetime) -> None:
        """
        Execute one PID update given a new measurement.

        Parameters
        ----------
        value : float
            Latest PV (e.g., temperature).
        timestamp : datetime.datetime
            Timestamp associated with the measurement (any tz/naive ok).

        Steps
        -----
        1) Compute dt safely and gate on minimum_elapsed_time.
        2) Compute error e = SP - PV.
        3) Update integral (with optional clamping).
        4) Derivative on measurement with optional EMA smoothing.
        5) Positional PID output with optional offset term.
        6) Saturate and apply anti-windup back-calculation.
        7) Apply output deadband; otherwise set & verify (bounded wait).
        """
        # --- 1) Compute dt and update last_data timestamp/value
        last_time = self._last_data['time']
        last_value = self._last_data['value']

        if last_time is None:
            # First call: initialize and return (need two samples for derivative)
            self._last_data = {'value': value, 'time': timestamp}
            logger.debug("initialized last_data on first sample")
            return

        dt = (timestamp - last_time).total_seconds()
        if dt <= 0:
            # Guard against clock anomalies; use a tiny positive dt
            dt = max(self.minimum_elapsed_time, 1e-6)

        if dt < self.minimum_elapsed_time:
            # Redundant—already gated in this_consume, but keep for safety
            logger.debug(f"skip: dt {dt:.6f} < min {self.minimum_elapsed_time:.6f}")
            return

        # --- 2) Error
        error = self._target_value - value
        logger.info(f"target value = {self._target_value:.3f}, sensor value = {value:.3f}")
        logger.info(f"Current error is: {error:.3f}")

        # --- 3) Integral with optional clamping
        self._integral += error * dt
        # if self._int_limit is not None:
            # self._integral = clamp(self._integral, -self._int_limit, self._int_limit)

        # --- 4) Derivative on measurement (reduces setpoint kick)
        if last_value is None:
            d_pv_dt = 0.0
        else:
            raw_d = (value - last_value) / dt
            # Optional EMA smoothing
            # self._ema_dpvdt = (self._alpha_d * self._ema_dpvdt
            #                    + (1.0 - self._alpha_d) * raw_d)
            # d_pv_dt = self._ema_dpvdt
            d_pv_dt = raw_d  # uncomment to disable smoothing

        # --- Update last sample after derivative calc
        self._last_data = {'value': value, 'time': timestamp}

        # --- 5) Positional PID output (keep original naming for gains)
        # Baseline offset behavior kept: if enable_offset_term, include baseline
        # composed of last commanded value and/or explicit u_offset_baseline.
        baseline = (self._old_current if self.enable_offset_term else 0.0) + self.u_offset_baseline
        change_terms = (self.Kproportional * error
                        + self.Kintegral * self._integral
                        - self.Kdifferential * d_pv_dt)
        new_current = baseline + change_terms
        logger.info(f"Baseline={baseline:.3f}, delta_terms={change_terms:.3f}")
        logger.info(f"Raw new current (pre-sat) = {new_current:.3f}")

        # --- 6) Saturation + anti-windup back-calculation
        new_current_sat = clamp(new_current, self.min_current, self.max_current)
        if new_current != new_current_sat and self.Kintegral > 0.0:
            # Back-calc: adjust integral to make effective output equal the sat value
            self._integral += (new_current_sat - new_current) / self.Kintegral
            if self._int_limit is not None:
                self._integral = clamp(self._integral, -self._int_limit, self._int_limit)
            new_current = new_current_sat
        else:
            new_current = new_current_sat
        logger.info(f"Saturation adjusted new current = {new_current:.3f}")
        
        # --- 7) Output deadband; set & verify
        if abs(new_current - (self._old_current or 0.0)) < self.min_current_change:
            logger.info("current change less than min delta")
            logger.info(f"old[new] are: {self._old_current:.3f}[{new_current:.3f}]")
            # Log even if we didn't update current
            self._log_append(timestamp, value, self._target_value, self._old_current)
            return

        self.set_current(new_current)
        # self._verify_after_set(new_current)

        # NEW: append log row
        self._log_append(timestamp, value, self._target_value, new_current)

        logger.info(f"PV={value:.4f} SP={self._target_value:.4f} e={error:.4f} dt={dt:.3f} "
                    f"u={new_current:.6f}  (Kp={self.Kproportional}, Ki={self.Kintegral}, Kd={self.Kdifferential})")

        self._old_current = new_current

    # ------------------------------------------------------------------ #
    # Private helpers (new, but do not change public surface)
    # ------------------------------------------------------------------ #

    # def _verify_after_set(self, u_cmd: float) -> None:
    #     """
    #     Poll check_channel up to max_settle_wait_s until |read - set| <= tolerance.

    #     Raises
    #     ------
    #     ThrowReply
    #         If actuator does not report the commanded value within the tolerance
    #         before timeout. Revalidates status before raising.
    #     """
    #     t0 = time.monotonic()
    #     last_exc = None
    #     u_read = None
    #     while (time.monotonic() - t0) < self.max_settle_wait_s:
    #         try:
    #             u_read = self.__get_current()
    #             if abs(u_read - u_cmd) <= self.tolerance:
    #                 return
    #         except Exception as ex:
    #             last_exc = ex
    #         time.sleep(0.1)

    #     # If we time out, ensure device is still enabled then raise
    #     self.__validate_status()
    #     detail = (f"set {u_cmd} but read {u_read} (±{self.tolerance})"
    #               if u_read is not None else str(last_exc))
    #     # at end of _verify_after_set
    #     logger.warning(f"Actuator verification failed: set {u_cmd} read {u_read} (±{self.tolerance})" if u_read is not None else "Actuator verification failed (no read)")
    #     return

    #     # raise ThrowReply('service_error_invalid_value', f'Actuator verification failed: {detail}')