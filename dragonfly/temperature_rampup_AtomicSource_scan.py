## Measurement Script for the Tectra H-flux atomic source 
## Temperature Scan (ramp down) with NIR spectrometer, with tectra hflux source
## 2025/05/16
## Measurement by: Brunilda Muçogllava

import time
import csv
import serial
from datetime import datetime

# Run Parameters
SETPOINT_VALUES = [1000, 1100, 1200, 1300, 1400, 1450]
HOLD_DURATION = 1800   # seconds
SAFE_INCREMENT = 200  # ramp step size (20°C)
RAMP_WAIT = 20        # delay between ramp steps (sec)

# File naming
now_timestamp = datetime.now().strftime("%Y%b%dT%H%M%S")
FILE_TO_LOG = f'tectra_measurement_data_{now_timestamp}.csv'

# Device Configuration
PORT = "COM22"
BAUDRATE = 9600
TIMEOUT = 1
DEVICE_ADDRESS = 1

# Initialize serial connection
ser = serial.Serial(
    port=PORT,
    baudrate=BAUDRATE,
    parity=serial.PARITY_NONE,
    bytesize=serial.EIGHTBITS,
    timeout=TIMEOUT
)

########################################################
# heater functions for sending read and write commands #


def send_command(command):
    """ Sends command to device and receives a reponse """
    ser.write(command)
    time.sleep(0.1)
    return ser.read(10) #response length is 10

def calculate_checksum(*args):
    """ Calculates the checksum as per AiBus specifications """
    checksum = sum(args) & 0xFFFF  #16-bit sum
    return checksum & 0xFF, (checksum >> 8) & 0xFF  #Return LSB, MSB

def read_parameter_command(param_code):
    """ Send command to read a parameter """
    read_command = [0x81, 0x81, 0x52, param_code, 0x00, 0x00]
    checksum_lsb, checksum_msb = calculate_checksum(param_code * 256 + 0x52 + 0x01)
    read_command.extend([checksum_lsb, checksum_msb])
    return bytearray(read_command)

def write_parameter_command(param_code, value):
    """ Send command to write/set a parameter """
    value_lsb, value_msb = value & 0xFF, (value >> 8) & 0xFF
    write_command = [0x81, 0x81, 0x43, param_code, value_lsb, value_msb]
    checksum_lsb, checksum_msb = calculate_checksum(param_code * 256 + 0x43 + 0x01 + value)
    write_command.extend([checksum_lsb, checksum_msb])
    return bytearray(write_command)


def parse_response(response):
    if len(response) == 10:
        b = [byte for byte in response]
        temperature = (b[1] * 256 + b[0]) * 0.1
        setpoint = (b[3] * 256 + b[2]) * 0.1
        output_value = b[4]
        alarm_status = b[5]
        param_value = b[7] * 256 + b[6]
        return temperature, setpoint, output_value, alarm_status, param_value
    else:
        print("Invalid response length")
        return [None] * 5


############################################################
################### PART WHERE THE RUN RUNS ################


def log_data():
    temp_response = send_command(read_parameter_command(0x00))
    temperature, setpoint, _, _, _ = parse_response(temp_response)

    p_term = parse_response(send_command(read_parameter_command(0x07)))[4]
    i_term = parse_response(send_command(read_parameter_command(0x08)))[4]
    d_term = parse_response(send_command(read_parameter_command(0x09)))[4]

    with open(FILE_TO_LOG, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().isoformat(), temperature, setpoint])

# Ramp functions
def temperature_ramp_up(start, target, step, delay):
    """ Safely and in small steps increase temperature to desired setpoint """
    current = start
    while current < target:
        current = min(current + step, target)
        send_command(write_parameter_command(0x00, current))
        time.sleep(delay)
        log_data()
    return current

def temperature_ramp_down(start, target, step, delay):
    """ Safely and in small steps decrease temperature to desired setpoint """
    current = start
    while current > target:
        current = max(current - step, target)
        send_command(write_parameter_command(0x00, current))
        time.sleep(delay)
        log_data()
    return current

# Initialize log file
with open(FILE_TO_LOG, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "Temperature(C)", "Setpoint(C)"])

# Main execution
if __name__ == "__main__":
    print("Turning device ON")
    send_command(write_parameter_command(0x1B, 0))  # Run
    time.sleep(1)

    send_command(write_parameter_command(0x06, 2))  # nPID mode
    print("Control mode: nPID")

    for setpoint in SETPOINT_VALUES:
        current_T = parse_response(send_command(read_parameter_command(0x00)))[0]
        current_T_x10 = int(current_T * 10)
        
        print(f"Current Temperature = {current_T:.1f} °C")
        print(f"Setting setpoint to {setpoint} °C")

        setpoint_x10 = int(setpoint * 10)
        if current_T_x10 <= setpoint_x10:
            print(f"Ramping up to {setpoint}")
            current_T_x10 = temperature_ramp_up(current_T_x10, setpoint_x10, SAFE_INCREMENT, RAMP_WAIT)
        else:
            print(f"Ramping down to {setpoint}")
            current_T_x10 = temperature_ramp_down(current_T_x10, setpoint_x10, SAFE_INCREMENT, RAMP_WAIT)

        print("Setpoint reached. Holding...")
        start_time = time.time()
        while time.time() - start_time < HOLD_DURATION:
            log_data()
            time.sleep(1)

    print("Done.")
    print("Turning device OFF")
    send_command(write_parameter_command(0x1B, 1))  # Stop
    
