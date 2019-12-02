'''
sensor logger now as a service
'''

from __future__ import absolute_import

# standard libs
import logging
import re

# internal imports
from dripline.core import Gogol, exceptions
from .postgres_interface import PostgreSQLInterface

__all__ = []
logger = logging.getLogger(__name__)


__all__.append('SensorLogger')
class SensorLogger(Gogol, PostgreSQLInterface):
    '''
    Project 8 slow control table implementation
    '''
    def __init__(self, sensor_type_map_table, sensors_key='sensor_value', sensor_type_column_name='type', sensor_type_match_column='endpoint_name', data_tables_dict={}, **kwargs):
        '''
        sensor_type_map_table (str): name of the child endpoint of this instance which provides access to the endpoint_id_map, which stores the sensor type
        sensor_type_column_name (str): name of the column to use for the return type (matched against keys in the data_tables_dict argument here)
        sensor_type_match_column (str): column against which to check for matches to the sensor name
        data_tables_dict (dict): dictionary mapping types (in the sensor_type_map_table) to child endpoints of this instance which provide access to the data_table for that type
        '''
        self.prefix = sensors_key
        kwargs.update({'keys':['{}.#'.format(sensors_key)]})
        PostgreSQLInterface.__init__(self, **kwargs)
        Gogol.__init__(self, **kwargs)
        logger.debug('bindings are: {}'.format(self._bindings))

        self._sensor_type_map_table = sensor_type_map_table
        self._sensor_type_column_name = sensor_type_column_name
        self._sensor_type_match_column = sensor_type_match_column
        self._sensor_types = {}
        self._data_tables = data_tables_dict
        self.service = self

    # add_endpoint is a mess here because of method overrides
    def add_endpoint(self, endpoint):
        # establish Spimescape add_endpoint as a starter
        Gogol.add_endpoint(self,endpoint)
        # forcing PostgreSQLInterface add_endpoint usage
        PostgreSQLInterface.add_endpoint(self,endpoint)


    def this_consume(self, message, basic_deliver):
        logger.debug("consuming message to: {}".format(basic_deliver.routing_key))
        ### Get the sensor name
        if not basic_deliver.routing_key.split('.')[0] == self.prefix:
            logger.warning("should not consume this message")
            return
        sensor_name = None
        if '.' in basic_deliver.routing_key:
            re_out = re.match(r'{}.(?P<from>\S+)'.format(self.prefix), basic_deliver.routing_key)
            sensor_name = re_out.groupdict()['from']
        # note that the following is deprecated in dripline 2.x, retained for compatibility
        else:
            raise exceptions.DriplineValueError('unknown sensor name')

        ### Get the type and table for the sensor
        this_type = None
        this_table = self.endpoints[self._sensor_type_map_table]
        this_type = this_table.do_select(return_cols=[self._sensor_type_column_name],
                                         where_eq_dict={self._sensor_type_match_column:sensor_name},
                                        )
        if not this_type[1]:
            logger.critical('endpoint with name "{}" was not found in database hence failed to log its value; might need to add it to the db'.format(sensor_name))
        else:
            this_table = self.endpoints[self._sensor_type_map_table]
            this_type = this_table.do_select(return_cols=[self._sensor_type_column_name],
                                             where_eq_dict={self._sensor_type_match_column:sensor_name},
                                            )
            self._sensor_types[sensor_name] = this_type[1][0][0]
            if not self._sensor_types[sensor_name] in self._data_tables:
                logger.critical('endpoint with name "{}" is not configured with a recognized type in the sensors_list table'.format(sensor_name))
                return
            this_data_table = self.endpoints[self._data_tables[self._sensor_types[sensor_name]]]

            ### Log the sensor value
            insert_data = {'endpoint_name': sensor_name,
                           'timestamp': message['timestamp'],
                          }
            for key in ['value_raw', 'value_cal', 'memo']:
                if key in message.payload:
                    insert_data[key] = message.payload[key]
            this_data_table.do_insert(**insert_data)
            logger.info('value logged for <{}>'.format(sensor_name))
