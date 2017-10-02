'''
Utility for monitoring logged values
'''

from __future__ import absolute_import

import datetime

from dripline.core import Gogol, Endpoint, exceptions, constants, fancy_doc

import logging
logger = logging.getLogger(__name__)

__all__ = []
__all__.append('SensorMonitor')
@fancy_doc
class SensorMonitor(Gogol):
    '''
    A generic service that will monitor logged values via the relevant alerts
    exchanges.  Each monitored endpoint should be configured as an element of
    the sensors list, and arbitrarily many alarms may be configured for each
    endpoint; alarms should be listed in decreasing severity as only the
    first alarm will be enacted.

    **NOTE**
    Any "keys" kwarg provided will be overwritten and bindings are to the alerts
    exchange as specified in Gogol and Service.
    '''

    def __init__(self,
                 sensors,
                 routing_key_base='sensor_value.',
                 **kwargs
                ):
        '''
        key_base (str): alerts exchange base, used to form complete names of alerts to bind
        sensors (list): list of endpoint and alarms to configure
        '''
        self.start_time = datetime.datetime.utcnow()
        self.configure_monitors(sensors)
        kwargs.update({'keys':[routing_key_base+x for x in self.monitors.keys()]})
        Gogol.__init__(self, **kwargs)


    @property
    def alarm_status(self):
        status = { x : { y : self.monitors[x][y] for y in self.monitors[x] if y not in ('alarms') } for x in self.monitors }
        return { 'value_raw' : status,
                 'value_cal' : '\n'.join(['{} : {}'.format(key,status[key]) for key in status]) }


    def silence_alarm(self, target, alarm_ct, endtime):
        if target not in self.monitors:
            raise exceptions.DriplineValueError("Invalid target <{}>, not found in {}".format(target, self.monitors.keys()))
        if alarm_ct not in range(len(self.monitors[target]['alarms'])):
            raise exceptions.DriplineValueError("Invalid alarm_ct provided <{}>, target only has {} alarms configured".format(endtime, len(self.monitors[target]['alarms'])))
        enddatetime = datetime.datetime.strptime(endtime,constants.TIME_FORMAT)
        if enddatetime < datetime.datetime.utcnow():
            self.monitors[target]['alarms'][alarm_ct].pop('silenced', None)
            self.monitors[target]['status'] = None
            return "Ignoring endtime in the past.  Alarm active!"
        if enddatetime > datetime.datetime.utcnow()+datetime.timedelta(1):
            raise exceptions.DriplineValueError("Invalid endtime provided <{}>, one day maximum silence interval".format(endtime))
        self.monitors[target]['alarms'][alarm_ct].update( { 'silenced' : enddatetime } )
        self.monitors[target]['status'] = 'SILENT'
        logger.warning('Silencing target {} alarm #{} until {}'.format(target, alarm_ct, endtime))


    def this_consume(self, message, method):
        sensor = method.routing_key[13:]
        if sensor not in self.monitors.keys():
            logger.warning('Received invalid routing key <{}> in method\n\t{}'.format(sensor,method))
            return
        if message.payload is None:
            logger.warning('Received invalid monitor payload!')
            return
        self.monitors[sensor].update( { 'timestamp' : message.timestamp,
                                        'payload' : message.payload } )
        logger.info('Consuming message from {}'.format(sensor))
        self.process_new_value(sensor)


    def process_new_value(self, sensor):
        monitor = self.monitors[sensor]
        payload = monitor['payload']
        logger.debug('Processing payload <{}>'.format(payload))
        alarm_list = []
        for alarm in monitor['alarms']:
            if 'silenced' in alarm:
                if datetime.datetime.utcnow() < alarm['silenced']:
                    logger.debug('Skipping {} during silenced interval'.format(alarm))
                    continue
                else:
                    alarm.pop('silenced')
                    logger.debug('Returning alarm to active state')
            try:
                value = payload[alarm['payload_field']]
                if not isinstance(value, (int,float)):
                    logger.critical('Invalid payload for sensor <{}>: {}'.format(sensor, value))
                    return
            except KeyError:
                logger.critical('Invalid payload field for sensor <{}>: {}'.format(sensor, alarm['payload_field']))
                return
            if alarm['averaging']:
                alarm['data_record'].append(value)
                if not len(alarm['data_record']) < alarm['averaging']:
                    del alarm['data_record'][0]
                    logger.debug('Only {} events in record'.format(len(alarm['data_record'])))
                value = sum(alarm['data_record'])*1./len(alarm['data_record'])
                logger.debug('Average value is {}'.format(value))
            if 'max_value' in alarm.keys() and value > alarm['max_value']:
                logger.info('Failed max_value check: value <{}> greater than limit <{}>'.format(value, alarm['max_value']))
                alarm_list.append('max_value')
            if 'min_value' in alarm.keys() and value < alarm['min_value']:
                logger.info('Failed min_value check: value <{}> less than limit <{}>'.format(value, alarm['min_value']))
                alarm_list.append('min_value')
            if 'max_slope' in alarm.keys():
                x = (datetime.datetime.strptime(monitor['timestamp'],constants.TIME_FORMAT)-self.start_time).total_seconds()
                alarm['timeseries'].append([x,value])
                if len(alarm['timeseries']) < alarm['slope_points']:
                    logger.debug('Only {} events in record'.format(len(alarm['timeseries'])))
                else:
                    while len(alarm['timeseries']) > alarm['slope_points']:
                        del alarm['timeseries'][0]
                    slope = (len(alarm['timeseries'])*sum([x[0]*x[1] for x in alarm['timeseries']])-\
                             sum([x[0] for x in alarm['timeseries']])*sum([x[1] for x in alarm['timeseries']]))/\
                            (len(alarm['timeseries'])*sum([x[0]**2 for x in alarm['timeseries']])-\
                             sum([x[0] for x in alarm['timeseries']])**2)
                    logger.debug('Calculated slope is {}'.format(slope))
                    if abs(slope) > alarm['max_slope']:
                        alarm_list.append('max_slope')

            result = ';'.join(alarm_list)
            self.process_alarms(alarm, result)

            # If alarm condition satisfied, ignore lower-level alarms
            if len(alarm_list) != 0:
                self.monitors[sensor]['status'] = 'ALARM'
                return
        if True in ['silenced' in alarm for alarm in self.monitors[sensor]]:
            self.monitors[sensor]['status'] = 'SILENT'
        else:
            self.monitors[sensor]['status'] = 'OK'


    def process_alarms(self, alarm, result):
        # If no alarms, reduce alarm_count as appropriate and return
        if len(result)==0:
            if alarm['alarm_limit'] and alarm['alarm_count']>0:
                alarm['alarm_count'] -= 1
            return
        # Check if alarm suppressed due to alarm_limit
        if alarm['alarm_limit'] and alarm['alarm_count']==alarm['alarm_limit']:
            if 'alarm_recurrence' not in alarm.keys():
                return
            interval = (datetime.datetime.utcnow()-alarm['last_alarm']).total_seconds()
            if interval < alarm['alarm_recurrence']:
                logger.debug('Suppressed alarm due to count over limit.  {} s since last alarm'.format(interval))
                return
            alarm['alarm_count'] -= 1
            logger.debug('De-incrementing alarm_count due to time elapsed since last_alarm')
        # Otherwise will emit alarm.
        message = alarm['alarm_message'].format(result)
        if alarm['alarm_limit']:
            alarm['alarm_count'] += 1
            if alarm['alarm_count'] == alarm['alarm_limit']:
                if alarm['alarm_recurrence']:
                    message += '.  Suppressing further alarms for {} s due to <alarm_limit> setting.'.format(alarm['alarm_recurrence'])
                else:
                    message += '.  Suppressing further alarms due to <alarm_limit> setting.'
            if alarm['alarm_recurrence']:
                alarm['last_alarm'] = datetime.datetime.utcnow()
        logger.critical(message)
        if 'set_condition' in alarm:
            self.provider.cmd('broadcast','set_condition', [alarm['set_condition']], timeout=5)


    def configure_monitors(self, sensors):
        for monitor in sensors:
            if 'target' not in monitor.keys():
                raise exceptions.DriplineValueError('No target provided for {}'.format(monitor))
            if 'alarms' not in monitor.keys() or not isinstance(monitor['alarms'],list):
                raise exceptions.DriplineValueError('No valid alarms provided for {}'.format(monitor))
            for alarm in monitor['alarms']:
                self.check_monitor_fields(alarm, monitor['target'])
            monitor.update( { 'status' : None,
                              'timestamp' : None,
                              'payload' : None } )

        self.monitors = {x.pop('target'):x for x in sensors}
        logger.debug('Configured monitors:\n{}'.format(self.monitors))


    def check_monitor_fields(self, alarm, target):
        if 'payload_field' not in alarm.keys():
            raise exceptions.DriplineValueError('No payload_field provided for {} : {}'.format(target,alarm))
        if 'alarm_message' not in alarm.keys():
            alarm.update({'alarm_message':'{} value raised <{{}}> alarm'.format(target)})
        if 'alarm_limit' not in alarm.keys():
            alarm.update({'alarm_limit':False})
        if alarm['alarm_limit']:
            if not isinstance(alarm['alarm_limit'],int):
                raise exceptions.DriplineValueError('Invalid alarm_limit type provided for {} : {}'.format(target,alarm))
            alarm.update({'alarm_count':0})
        if 'alarm_recurrence' in alarm.keys():
            if not alarm['alarm_recurrence']>0 and isinstance(alarm['alarm_recurrence'],(int,float)):
                raise exceptions.DriplineValueError('Invalid alarm_recurrence provided for {} : {}'.format(target,alarm))
            alarm.update({'last_alarm':self.start_time})
        if 'set_condition' in alarm.keys():
            if not isinstance(alarm['set_condition'],int):
                raise exceptions.DriplineValueError('Invalid set_condition type provided for {} : {}'.format(target,alarm))
        if 'averaging' not in alarm.keys():
            alarm.update({'averaging':False})
        if alarm['averaging']:
            if not alarm['averaging']>0 and isinstance(alarm['averaging'],int):
                raise exceptions.DriplineValueError('Invalid averaging provided for {} : {}'.format(target,alarm))
            alarm.update({'data_record':[]})
        if 'max_value' in alarm.keys():
            self.check_if_float('max_value',alarm,target)
        if 'min_value' in alarm.keys():
            self.check_if_float('min_value',alarm,target)
        if 'max_slope' in alarm.keys():
            self.check_if_float('max_slope',alarm,target)
            if 'slope_points' not in alarm.keys():
                raise exceptions.DriplineValueError('Setting slope_points required with max_slope for {} : {}'.format(target,alarm))
            alarm.update({'timeseries':[]})


    def check_if_float(self,key,alarm,target):
        if not isinstance(alarm[key],(int,float)):
            try:
                alarm[key] = float(alarm[key])
            except ValueError:
                raise exceptions.DriplineValueError('Invalid {} provided for {} : {}'.format(key,target,alarm))
