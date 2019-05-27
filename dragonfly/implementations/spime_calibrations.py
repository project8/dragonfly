'''
Welcome to the 'calibration zoo'
All defined calibration functions go here, for import by spime_endpoints to calibrate the various spimes.
'''

import math

from dripline.core.exceptions import DriplineValueError

import logging
logger = logging.getLogger(__name__)

def acquisition_calibration(value):
    '''Calibration for the lockin_curve_status endpoint'''
    if value[0] == 0:
        status = 'done, {} curve(s) available with {} points'.format(value[1], value[3])
    elif value[0] == 1:
        status = 'running, {} points collected'.format(value[3])
    else:
        raise DriplineValueError('unexpected status byte value: {}'.format(value[0]))
    return status


def status_calibration(value):
    '''Calibration for the lockin_status endpoint'''
    lookup = { 0 : "command complete",
               1 : "invalid command",
               2 : "command parameter error",
               3 : "reference unlock",
               4 : "overload",
               5 : "new ADC values available after external trigger",
               6 : "asserted SRQ",
               7 : "data available" }
    status = []
    for i in range(8):
        if value & 1<<i:
            status.append(lookup[i])
    return "; ".join(status)


def leak_valve_status_calibration(value):
    '''Calibration for the leak_valve_status endpoint'''
    value = str(value).zfill(8)
    logger.debug('Calibrating padded value <{}>'.format(value))
    status = []
    comm = value[0]
    mode = value[1]
    other = value[2:]
    if comm == '1':
        status.append("remote communication")
    else:
        status.append("WARNING: unknown communication")
    if mode == '2':
        status.append("valve in position control")
    elif mode == '3':
        status.append("valve closed")
    elif mode == '4':
        status.append("valve open")
    elif mode == 'D':
        status.append("WARNING: safety mode, remove motor interlock")
    else:
        status.append("WARNING: unknown mode")
    if other != '000000':
        status.append("WARNING: unknown status flags")
    return "; ".join(status)


def pt100_calibration(resistance):
    '''Calibration for the (many) muxer pt100 temperature sensor endpoints'''
    r = resistance
    value = ((r < 2.2913) * ((3.65960-r)*(-6.95647+r/0.085)/1.36831 + (r-2.2913)*(10.83979+r/.191)/1.36831 ) + # extrapolation to too small temperature
        (2.2913 <= r and r < 3.65960) *((3.65960-r)*(-6.95647+r/0.085)/1.36831 + (r-2.2913)*(10.83979+r/.191)/1.36831 ) +
        (3.6596 <= r and r < 9.38650) *((9.38650-r)*(10.83979+r/0.191)/5.72690 + (r-3.6596)*(23.92640+r/.360)/5.72690) +
        (9.3865 <= r and r < 20.3800) *((20.3800-r)*(23.92640+r/0.360)/10.9935 + (r-9.3865)*(29.17033+r/.423)/10.9935) +
        (20.380 <= r and r < 29.9890) *((29.9890-r)*(29.17033+r/0.423)/9.60900 + (r-20.380)*(29.10402+r/.423)/9.60900) +
        (29.989 <= r and r < 50.7880) *((50.7880-r)*(29.10402+r/0.423)/20.7990 + (r-29.989)*(25.82396+r/.409)/20.7990) +
        (50.788 <= r and r < 71.0110) *((71.0110-r)*(25.82396+r/0.409)/20.2230 + (r-50.788)*(22.47250+r/.400)/20.2230) +
        (71.011 <= r and r < 90.8450) *((90.8450-r)*(22.47250+r/0.400)/19.8340 + (r-71.011)*(18.84224+r/.393)/19.8340) +
        (90.845 <= r and r < 110.354) *((110.354-r)*(18.84224+r/0.393)/19.5090 + (r-90.845)*(14.84755+r/.387)/19.5090) +
        (110.354 <= r and r < 185) * (14.84755+r/.387) +
        (185. <= r) * (0))
    if value == 0:
        value = None
    return value


def cernox_calibration_chebychev(resistance,serial_number):
    '''Calibration for the muxer cernox temperature sensor endpoints'''
    data={
        73819:[((2.84146227936,3.92053008093),(54.238901,-44.615418,9.800540,-1.373596,0.137863,-0.004419)),
               ((2.17544340838,2.99571912372),(187.259060,-119.735282,19.990658,-2.662007,0.418343,-0.068467,0.009811,-0.003678))]
    }
    Z=math.log10(resistance)
    logger.debug(Z)
    tmp=data[serial_number]
    this_data = None
    for this_data_range in tmp:
        if (this_data_range[0][0]<Z and Z<this_data_range[0][1]):
            this_data = this_data_range
            break
    if this_data is None:
        return None
    ZL = this_data[0][0]
    ZU = this_data[0][1]
    k = ((Z-ZL)-(ZU-Z))/(ZU-ZL)
    temperature = 0
    i=0
    for A_i in this_data[1]:
        temperature += A_i*math.cos(i*math.acos(k))
        i+=1
    return temperature


def cernox_calibration(resistance, serial_number):
    '''Calibration for the muxer cernox temperature sensor endpoints'''
    data = {
            1912:[(45.5, 297), (167.5, 77), (310.9, 40), (318.2, 39), (433.4, 28)],
            1929:[(11.29, 350), (45.5, 297), (187.5, 77), (440.9, 30.5), (1922, 6.7), (2249, 5.9), (3445, 4.3), (4611, 3.5), (6146, 3), (8338, 2.5), (11048, 2.1), (11352, 2)], #note that the (11.29, 350 value is a linear extension of the next two points, not an empirical value... the function should actually be changed to use the first or last interval for out of range readings)
            33122:[(30.85, 350), (47.6, 300), (81.1, 200), (149, 100), (180, 80), (269, 50), (598, 20)], #note that the (30.85,350 value is a linear extension of the next two points, not an empirical value... the function should actually be changed to use the first or last interval for out of range readings)
            31305:[(62.8, 300), (186, 78), (4203, 4.2)],
            43022:[(68.6, 300), (248, 78), (3771, 4.2)],
            87771:[(68.3, 305), (211, 77), (1572, 4.2)],
            87791:[(66.9, 305), (209, 79), (1637, 4.2)],
            87820:[(69.2, 305), (212, 77), (1522, 4.2)],
            87821:[(68.7, 305), (218, 77), (1764, 4.2)],
            #87821:[(56.21, 276.33), (133.62, 77), (1764, 4.2)], #recal
           }
    this_data = data[serial_number]
    this_data.sort()
    last = ()
    next = ()
    for pt in this_data:
        if pt[0] < resistance:
            last = pt
        elif pt[0] == resistance:
            return pt[1]
        else:
            next = pt
            break
    if not next or not last:
        return None
    m = (math.log(next[1])-math.log(last[1])) / (math.log(next[0])-math.log(last[0]))
    b = math.log(next[1]) - m * math.log(next[0])
    return math.exp(math.log(resistance)*m+b)
