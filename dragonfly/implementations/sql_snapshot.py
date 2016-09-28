'''
A class for obtaining snapshots of the slow_control database

Note: sqlalchemy is required in the methods of this class
'''
from __future__ import absolute_import
__all__ = []

# std libraries
import json
import os
import types
import traceback


# 3rd party libraries
try:
    import sqlalchemy
except ImportError:
    pass
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from datetime import datetime
from itertools import groupby
import collections

# local imports
from dripline.core import Provider, Endpoint, exceptions
from dripline.core.utilities import fancy_doc
from dragonfly.implementations import PostgreSQLInterface, SQLTable

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

__all__.append('SQLSnapshot')

class SQLSnapshot(SQLTable):

    def __init__(self, table_name, schema, *args, **kwargs):
        '''
        '''
        if not 'sqlalchemy' in globals():
                raise ImportError('SQLAlchemy not found, required for SQLSnapshot class')
        SQLTable.__init__(self, table_name, schema, *args, **kwargs)

    def get_logs(self, start_timestamp, end_timestamp):
        '''
        Both inputs must be specified as either date only 'Y-M-D' or date with time 'Y-M-D HH:MM:SS'
        start_timestamp (str): oldest timestamp for query into database
        ending_timesamp (str): most recent timestamp for query into database
        '''    
        start_timestamp = str(start_timestamp)
        end_timestamp = str(end_timestamp)                

        # Parsing timestamps
        self._try_parsing_date(start_timestamp)
        self._try_parsing_date(end_timestamp)
        if not end_timestamp > start_timestamp:
            raise exceptions.DriplineValueError('end_timestamp ("{}") must be > start_timestamp ("{}")!'.format(end_timestamp,start_timestamp))
        
        # Connect to id map table + assign alises
        self._connect_id_table()          
        t = self.table.alias()
        id_t = self.it.alias()

        # Select query + result
        s = sqlalchemy.select([id_t.c.endpoint_name,t.c.timestamp,t.c.value_raw,t.c.value_cal]).select_from(t.join(id_t,t.c.endpoint_id == id_t.c.endpoint_id))
        logger.debug('querying database for entries between "{}" and "{}"'.format(start_timestamp,end_timestamp))
        s = s.where(sqlalchemy.and_(t.c.timestamp>=start_timestamp,t.c.timestamp<=end_timestamp)).order_by(id_t.c.endpoint_name.asc())
        try:
            query_return = self.provider.engine.execute(s).fetchall()
        except exceptions.DriplineDatabaseError as dripline_error:
            logger.error('{}; in executing SQLAlchemy select statement'.format(dripline_error.message))
            return
        if not query_return:
            logger.warning('no entries found between "{}" and "{}"'.format(start_timestamp,end_timestamp))

        # Counting how many times each endpoint is present
        endpoint_name_raw = []
        endpoint_dict = {}
        for row in query_return:
            endpoint_name_raw.append(str(row['endpoint_name']))
        for key,group in groupby(endpoint_name_raw):
            endpoint_dict[key] = len(list(group))
        # Ordering according to SQL query return
        endpoint_dict = collections.OrderedDict(sorted(endpoint_dict.items(),key=lambda pair:pair[0].lower()))

        # Parsing result
        val_dict = {'timestamp':None,'value_raw':None,'value_cal':None}
        val_raw_dict = {}
        val_cal_list = []
        index = 0
        for endpoint,times in endpoint_dict.items():
            val_raw_dict[endpoint] = []
            ept_timestamp_list = []
            for i in range(times):
                val_raw_dict[endpoint].append(val_dict.copy())
                query_row = query_return[index]
                val_raw_dict[endpoint][i]['timestamp'] = query_row['timestamp'].isoformat()
                val_raw_dict[endpoint][i]['value_raw'] = query_row['value_raw']
                val_raw_dict[endpoint][i]['value_cal'] = query_row['value_cal']
                ept_timestamp_list.append('{} {{{}}}'.format(val_raw_dict[endpoint][i]['value_cal'],val_raw_dict[endpoint][i]['timestamp']))
                index += 1
            ept_timestamp_results = ', '.join(ept_timestamp_list)
            val_cal_list.append('{} -> {}'.format(endpoint,ept_timestamp_results))
        
        # JSON formatting
        val_raw_json = json.dumps(val_raw_dict,indent=4,sort_keys=True,separators=(',',':'))

        return {'value_raw': val_raw_json, 'value_cal': '\n'.join(val_cal_list)}


    def get_latest(self, timestamp, endpoint_list):
        '''
        start_timestamp (str): oldest timestamp for query into database. Format must be either date only 'Y-M-D' or date with time 'Y-M-D HH:MM:SS'
        endpoint_list (list of str): list of endpoint names (str) of interest
        '''
        timestamp = str(timestamp)
        endpoint_list = [name for name in endpoint_list.strip('[]').split(',')]              

        # Parsing timestamp
        self._try_parsing_date(timestamp)

        # Connect to id map table + assign alises
        self._connect_id_table()
        t = self.table.alias()
        id_t = self.it.alias()

        # Select query + result
        val_cal_list = []
        val_raw_dict = {}

        for name in endpoint_list:

            logger.debug('querying database for endpoint with name "{}"'.format(name))
            s = sqlalchemy.select([id_t.c.endpoint_id]).where(id_t.c.endpoint_name == name)
            try:
                query_return = self.provider.engine.execute(s).fetchall()
            except exceptions.DriplineDatabaseError as dripline_error:
                logger.error('{}; in executing SQLAlchemy select statement to obtain endpoint_id for endpoint "{}"'.format(dripline_error.message,name))
                return
            if not query_return:
                logger.error('endpoint with name "{}" not found in database'.format(name))
                continue
            else:
                ept_id = query_return[0]['endpoint_id']
            logger.debug('endpoint id "{}" matched to endpoint "{}"'.format(ept_id,name))
            s = sqlalchemy.select([t]).where(sqlalchemy.and_(t.c.endpoint_id == ept_id,t.c.timestamp < timestamp))
            s = s.order_by(t.c.timestamp.desc()).limit(1)
            try:
                query_return = self.provider.engine.execute(s).fetchall()
            except exceptions.DriplineDatabaseError as dripline_error:
                logger.error('{}; in executing SQLAlchemy select statement for endpoint "{}"'.format(dripline_error.message,name))
                return
            if not query_return:
                logger.error('no records found before "{}" for endpoint "{}" in database'.format(timestamp,name))
                continue
            else:
                val_raw_dict[name] = (query_return[0]['value_cal'],query_return[0]['timestamp'].isoformat())
                val_cal_list.append('{} -> {} {{{}}}'.format(name,val_raw_dict[name][0],val_raw_dict[name][1]))
                              
        return {'value_raw': val_raw_dict, 'value_cal': '\n'.join(val_cal_list)}


    def _try_parsing_date(self, timestamp):
        '''
        Checks if timestamp (str) is in correct format for database query
        '''        
        for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(timestamp, fmt)
            except ValueError:
                pass
        raise exceptions.DriplineDatabaseError('"{}" is not a valid timestamp format'.format(timestamp))


    def _connect_id_table(self):
        '''
        Connects to the 'endpoint_id_map' table in database
        '''        
        try:
            self.it = sqlalchemy.Table('endpoint_id_map',self.provider.meta, autoload=True, schema=self.schema)
        except exceptions.DriplineDatabaseError as dripline_error:
            logger.error('{}; when establishing connection to the "endpoint_id_map" table'.format(dripline_error.message))

