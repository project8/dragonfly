#!/usr/bin/python
''' dpph_scan
Make a dpph based field measurement
'''

from __future__ import absolute_import


import csv
import time

import pika
import numpy

from dripline.core import DriplineParser, constants, Service, message, exceptions

import logging
logger = logging.getLogger('dpph_scan')

def scdb_log(broker, sensor, value_raw, value_cal=None, extra_memo=None, **kwargs):
    # construct log info
    to_log = {'from':sensor,
              'values':{'value_raw': value_raw,
                       'memo': 'logged manually',
                      },
             }
    if value_cal is not None:
        to_log['values']['value_cal'] = value_cal
    if extra_memo is not None:
        to_log['values']['memo'] += extra_memo
    logger.debug('logging to sensor: {}'.format(sensor))
    logger.debug('with info:\n{}'.format(to_log['values']))

    # make connection
    # note that we're not consuming, so the exchange and key values here don't really matter
    conn = Service(amqp_url = broker,exchange = 'alerts',keys = '#')
    conn.send_alert(severity='sensor_value.'.format(sensor), alert=to_log)
    logger.info('log sent')


def scdb_query(broker,sensor):
    request_verb = 'get'
    msgop = getattr(constants, 'OP_'+request_verb.upper())
    conn = Service(amqp_url = broker,
                   exchange = 'requests',
                   keys = '#'
                  )

    values = []
    payload = {}
    payload.update({'values':values})
    logger.debug('payload will be: {}'.format(payload))
    request = message.RequestMessage(msgop=msgop, payload=payload)
    try:
        reply = conn.send_request(sensor, request)
    except exceptions.DriplineException as dripline_error:
        logger.warning(dripline_error.message)
        return
    if not isinstance(reply, message.Message):
        result = message.Message.from_msgpack(reply)
    else:
        result = reply
    print_prefix = '->'.join([sensor])
    color = ''
    if not result.retcode == 0:
        color = '\033[91m'
    print('{color}{}: {}\033[0m'.format(print_prefix, result.payload, color=color))
    return result


def _get(name, connection):
    payload = {}
    payload.update({'values':[]})
    request = message.RequestMessage(msgop=constants.OP_GET,payload=payload)
    reply = connection.send_request(name, request)
    if not isinstance(reply, message.Message):
        result = message.Message.from_msgpack(reply)
    else:
        result = reply
    result_message = result.payload
    logger.debug("{}-> {}".format(name, result_message))
    return result_message


def get_data(connection):
    if not connection:
        logger.warning("no connection, can't get data")
        raise ValueError('no connection')
    data = {}
    # ensure lockin config
    logger.info('ensure_setup')
    _get('lockin_ensure_setup', connection)
    # trigger taking data
    logger.info('start_taking_data')
    result = _get('lockin_take_data', connection)
    # wait for data taking to finish... would be nice to sleep for the nomial data-taking time prior to starting to poll
    while not result == 'done':
        time.sleep(0.2)
        npts = _get('lockin_curve_status', connection)
        result = _get('lockin_status', connection)
        logger.info('collected {}/400? points'.format(npts.split(',')[-1].strip()))
    # get data
    result = _get('lockin_mag_data', connection)
    data['amplitude'] = numpy.array(result.strip('\0').replace('\x00','').split(), dtype=float)
    result = _get('lockin_adc_data', connection)
    data['sweep_out'] = numpy.array(result.strip('\0').replace('\x00','').split(), dtype=float)
    # Save additional data
    result = _get('lockin_x_data', connection)
    data['lockin_x_data'] = numpy.array(result.strip('\0').replace('\x00','').split(), dtype=float)
    result = _get('lockin_y_data', connection)
    data['lockin_y_data'] = numpy.array(result.strip('\0').replace('\x00','').split(), dtype=float)


    return data


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


def FrequencyToField(frequency):
    '''
    Args:
        frequency (float): the resonant frequency [Hz] to convert
    Returns:
        value of the magnetic field for that frequency, in kG
    '''
    geff = 2.0036
    charge_over_mass = 1.758e11
    # factor of 10 is for T->kG
    field = (4 * numpy.pi * 10. / (geff * charge_over_mass) * frequency)
    logger.info('converted {} [Hz] -> {} [kG]'.format(frequency, field))
    return field


def main(broker, frequency_limits, output, store, width, filter, **kwargs):
    ##### Connect to slow controls
    logger.info('broker is: {}'.format(broker))
    try:
        connection = Service(amqp_url=broker, exchange='requests', keys = ['#'])
    except pika.exceptions.AMQPConnectionError:
        logger.error('unable to connect to broker')
        #return
        connection = False

    ##### confirm frequency limits
    logger.info('frequency limits are: {}'.format(frequency_limits))
    if not frequency_limits:
        # something to get them from the sweeper
        logger.warning('sweeper interactions are all hard-coded here right now...')

        result = connection.send_request(target='hf_start_freq', request=message.RequestMessage(msgop=constants.OP_GET, payload={'values':{}}))
        start_freq = float(result['payload']['value_raw'])
        logger.info('got a start of: {}'.format(start_freq))
        result = connection.send_request(target='hf_stop_freq', request=message.RequestMessage(msgop=constants.OP_GET, payload={'values':{}}))
        stop_freq = float(result['payload']['value_raw'])
        logger.info('got a stop of: {}'.format(stop_freq))
        # also get the sweeper's sweep params and setup data taking options
        result = connection.send_request(target='hf_number_sweep_points', request=message.RequestMessage(msgop=constants.OP_GET, payload={'values':{}}))
        n_sweep_pts = float(result['payload']['value_raw'])
        result = connection.send_request(target='hf_dwell_time', request=message.RequestMessage(msgop=constants.OP_GET, payload={'values':{}}))
        hf_dwell = float(result['payload']['value_raw'])
        sweep_time = n_sweep_pts * hf_dwell
        result = connection.send_request(target='lockin_instrument', request=message.RequestMessage(msgop=constants.OP_CONFIG, payload={'values':['number_of_points']}))
        n_daq_points = float(result.payload)

        daq_time = 45. + sweep_time
        daq_sampling = 5.0 * (1 + numpy.ceil((daq_time/n_daq_points) / 0.005)) # must be in ms and multiple of 5 ms
        logger.info('\nsweep time is: {}\nsampling time will be: {}'.format(
                        n_sweep_pts*hf_dwell,
                        n_daq_points*daq_sampling/1e3
                   ))
        logger.info('setting lockin sampling rate to {} ms'.format(daq_sampling))
        result = connection.send_request(target='lockin_instrument', request=message.RequestMessage(msgop=constants.OP_CONFIG, payload={'values':['sampling_interval', int(daq_sampling)]}))

    else:
        start_freq = min(map(float, frequency_limits))
        stop_freq = max(map(float, frequency_limits))
    
    ######## get lock-in data
    # get data
    logger.info('now get data from lockin')
    lockin_data = get_data(connection)
    # map adc values to frequencies
    logger.info('map sweep out to frequencies')
    m = (stop_freq - start_freq) / (10.)
    lockin_data['frequencies'] = start_freq + m * lockin_data['sweep_out']
    lockin_data['amplitude'] = lockin_data['lockin_x_data'] + 1j*lockin_data['lockin_y_data']
    # pass data to filter
    logger.info('do optimal filter on output')
    filter_data = WeinerFilter(lockin_data['frequencies'], lockin_data['amplitude'], width=width, target=filter)
    max_freq_index = numpy.abs(filter_data['result']) == numpy.abs(filter_data['result']).max()
    res_freq = filter_data['freqs'][max_freq_index]
    # save raw output to file if requested
    if output:
        output_file = open(output, 'w')
        csv_writer = csv.writer(output_file)
        csv_writer.writerow(['sweep_out',
                             'sweep_freqs',
                             'lockin_signal',
                             'lockin_x_data',
                             'lockin_y_data',
                             'filter_freqs',
                             'filter_target',
                             'filter_result',
                            ])
        csv_writer.writerows(zip(lockin_data['sweep_out'],
                                 lockin_data['frequencies'],
                                 lockin_data['amplitude'],
                                 lockin_data['lockin_x_data'],
                                 lockin_data['lockin_y_data'],
                                 filter_data['freqs'],
                                 filter_data['target'],
                                 filter_data['result'],
                                ))
        output_file.close()
    # make plot if requested
    # prompt user for approval to log if requested
    # print field result
    logger.info("compute field")
    field = FrequencyToField(filter_data['freqs'][filter_data['result']==filter_data['result'].max()])
    #print('value is: {}'.format(field))

    #########
    # Store the results to the database
    result = None
    if store:
        sensor = 'string_pot_resistance'
        result = scdb_query(broker=broker,sensor=sensor)
        # First, the Z position
        scdb_log(broker=broker, sensor=sensor, value_raw=result.payload['value_raw'], value_cal=result.payload['value_cal'])
        # Then the dpph value
        scdb_log(broker=broker, sensor='dpph', value_raw=field[0], value_cal=field[0])
        logger.info('Resuls logged to database')
    #########
    # Print Results
    result_str = ''
    if result is not None:
        result_str = 'String Z Position = {:.2f} [mm]; '.format(result.payload['valuecal'])
    result_str += 'Field = {:.5f} [kG]'.format(field[0])
    logger.log(25, result_str)


if __name__ == '__main__':
    scan_doc = '''
               dpph_scan performs a dpph scan and field estimate
               '''
    parser = DriplineParser(description=scan_doc,
                            extra_logger=logger,
                            amqp_broker=True,
                            tmux_support=True,
                            twitter_support=True,
                           )
    # an option for outputting raw data
    parser.add_argument('-o', '--output', default=False)
    # an option for outputting a grahic
    # an option for passing in the sweeper limits
    parser.add_argument('-f', '--frequency-limits', nargs=2, default=[])
    # an option to log the result (have this prompt the user first?)
    parser.add_argument('-s', '--store',
                        help='send an alert message logging both the z position and dpph field result',
                        default=False,
                        action='store_const',
                        const=True, #value if option given with no argument
                       )
    parser.add_argument('-w', '--width',
                        help='specify resonance width in Hz, for a gaussian filter it is sigma, for a lorentzian it is FWMH',
                        default=10.e6,
                        action='store',
                        type=float,
                       )
    parser.add_argument('--filter',
                        help='specify what filter function to use',
                        choices=['gaussian', 'lorentzian'],
                        default='lorentzian',
                        action='store',
                       )
    
    args = parser.parse_args()
    main(**vars(args))