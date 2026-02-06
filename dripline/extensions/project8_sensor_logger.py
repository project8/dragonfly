'''
A Postgres Interface-based logger
'''

from __future__ import absolute_import

# standard libs
import logging
import re

# 3rd party libs
import sqlalchemy

# internal imports
from dripline.core import AlertConsumer
from dripline.implementations.postgres_interface import PostgreSQLInterface

__all__ = []
logger = logging.getLogger(__name__)


__all__.append('Project8SensorLogger')
class Project8SensorLogger(AlertConsumer, PostgreSQLInterface):
    '''
    A custom sensor logger tailored to the project 8 database structure.
    '''
    def __init__(self, sensor_type_map_table, data_tables_dict={}, **kwargs):
        '''
        sensor_type_map_table (str): name of the child endpoint of this instance which provides access to the endpoint_id_map, which stores the sensor type
        data_tables_dict (dict): dictionary mapping types (in the sensor_type_map_table) to child endpoints of this instance which provide access to the data_table for that type
        '''
        AlertConsumer.__init__(self, add_endpoints_now=False, **kwargs)
        PostgreSQLInterface.__init__(self, **kwargs)
        
        self._sensor_type_map_table = sensor_type_map_table
        self._data_tables = data_tables_dict

        self.connect_to_db(self.auth)

        self.add_endpoints_from_config()

    # add_endpoint is a mess here because of the diamond inheritance, so let's be explicit
    def add_child(self, endpoint):
        AlertConsumer.add_child(self, endpoint)
        self.add_child_table(endpoint)

    def process_payload(self, a_payload, a_routing_key_data, a_message_timestamp):
        try:
            # get the type and table for the sensor
            this_type = None
            this_type = self.sync_children[self._sensor_type_map_table].do_select(return_cols=["type"], 
                                                                                  where_eq_dict=a_routing_key_data)
            # add safty check, and see if the key is contained in the table otherwise generate meaningful error message
            try:
                table_name = self._data_tables[this_type[1][0][0]]
            except:
                raise Exception(f"{a_routing_key_data} is not in database, see {this_type}")
            this_data_table = self.sync_children[table_name]

            # combine data sources
            insert_data = {'timestamp': a_message_timestamp}
            insert_data.update(a_routing_key_data)
            insert_data.update(a_payload.to_python())
            logger.info(f"Inserting {a_routing_key_data} in table {table_name}; data are:\n{insert_data}")

            # do the insert
            insert_return = this_data_table.do_insert(**insert_data)
            logger.debug(f"Return from insertion: {insert_return}")
            logger.info("finished processing data")
        except sqlalchemy.exc.SQLAlchemyError as err:
            logger.critical(f'Received SQL error while doing insert: {err}')
        except Exception as err:
            logger.critical(f'An exception was raised while processing a payload to insert: {err}')
