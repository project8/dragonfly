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
    __all__.append('SQLSnapshot')
except ImportError:
    pass
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from datetime import datetime
from itertools import groupby
import collections

# local imports
from dripline.core import Provider, Endpoint
from dripline.core.exceptions import *
from dripline.core.utilities import fancy_doc
from dragonfly.implementations import PostgreSQLInterface, SQLTable

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SQLSnapshot(SQLTable):

        def __init__(self, table_name, schema, *args, **kwargs):
                '''
                '''
                SQLTable.__init__(self, table_name, schema, *args, **kwargs)

        def get_logs(self, start_timestamp, end_timestamp):

                '''
                Both inputs must be specified as either date only 'Y-M-D' or date with time 'Y-M-D HH:MM:SS'
                start_timestamp (str): oldest timestamp for query into database
                ending_timesamp (str): most recent timestamp for query into database
                '''    

                start_timestamp = str(start_timestamp)
                end_timestamp = str(end_timestamp)

                logger.debug('start_timestamp is "{}" and of {}\n'.format(start_timestamp,type(start_timestamp)))
                logger.debug('end_timestamp is "{}" and of {}\n'.format(end_timestamp,type(end_timestamp)))
  
                # Creating the id map table
                self.it = sqlalchemy.Table('endpoint_id_map',self.provider.meta, autoload=True, schema=self.schema)                

                # Parsing timestamps
                self._try_parsing_date(start_timestamp)
                self._try_parsing_date(end_timestamp)
                if not end_timestamp > start_timestamp:
                        raise Exception('end_timestamp ("{}") must be > start_timestamp ("{}")!'.format(end_timestamp,start_timestamp))          

                # Table aliases
                t = self.table.alias()
                id_t = self.it.alias()

                # Select query + result
                s = sqlalchemy.select([id_t.c.endpoint_name,t.c.timestamp,t.c.value_raw,t.c.value_cal]).select_from(t.join(id_t,t.c.endpoint_id == id_t.c.endpoint_id))
                s = s.where(sqlalchemy.and_(t.c.timestamp>=start_timestamp,t.c.timestamp<=end_timestamp)).order_by(id_t.c.endpoint_name.asc())
                query_return = self.provider.engine.execute(s).fetchall()

                # Counting how many times each endpoint is present
                endpoint_name_raw = []
                endpoint_dict = {}
                for i,row in enumerate(query_return):
                        endpoint_name_raw.append(query_return[i][0])
                for key,group in groupby(endpoint_name_raw):
                        endpoint_dict[key] = len(list(group))
                # Ordering according to SQL query return
                endpoint_dict = collections.OrderedDict(sorted(endpoint_dict.items(),key=lambda pair:pair[0].lower()))

                # Parsing result
                val_dict = {'timestamp':None,'value_raw':None,'value_cal':None}
                results= {}
                index = 0
                for endpoint,times in endpoint_dict.items():
                        results[endpoint] = []
                        for i in range(times):
                                results[endpoint].append(val_dict.copy())
                                row = query_return[index]
                                results[endpoint][i]['timestamp'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                                results[endpoint][i]['value_raw'] = row['value_raw']
                                results[endpoint][i]['value_cal'] = row['value_cal']
                                index += 1
                
                # JSON formatting
                results_json = json.dumps(results,indent=4,sort_keys=True,separators=(',',':'))
                print(results_json)
                return

        def get_latest(self, timestamp, endpoint_list):

                '''
                start_timestamp (str): oldest timestamp for query into database. Format must be either date only 'Y-M-D' or date with time 'Y-M-D HH:MM:SS'
                endpoint_list (list of str): list of endpoint names (str) of interest
                '''

                timestamp = str(timestamp)
                endpoint_list = [str(endpoint) for endpoint in endpoint_list]

                logger.debug('timestamp is "{}" and of {}\n'.format(timestamp,type(timestamp)))
                logger.debug('endpoint_list is "{}" and of {}\n'.format(endpoint_list,type(endpoint_list)))

                # Creating the id map table
                self.it = sqlalchemy.Table('endpoint_id_map',self.provider.meta, autoload=True, schema=self.schema)                

                # Parsing timestamp
                self._try_parsing_date(timestamp)

                # Table aliases
                t = self.table.alias()
                id_t = self.it.alias()

                # Select query + result
                result_list = []
                val_cal_list = []
                val_raw_dict = {}
                for name in endpoint_list:

                        s = sqlalchemy.select([id_t.c.endpoint_id]).where(id_t.c.endpoint_name == name)
                        result = self.provider.engine.execute(s).fetchall()
                        if not result:
                                print('endpoint with name "{}" not found in database'.format(name))
                                continue
                        else:
                                ept_id = result[0]['endpoint_id']
                        s = sqlalchemy.select([t]).where(sqlalchemy.and_(t.c.endpoint_id == ept_id,t.c.timestamp < timestamp))
                        s = s.order_by(t.c.timestamp.desc()).limit(1)
                        result = self.provider.engine.execute(s).fetchall()
                        if not result:
                                print('no records found before "{}" for endpoint "{}" in database'.format(timestamp,name))
                                continue
                        else:
                                val_raw_dict[name] = result[0]
                                val_cal_list.append('{} -> {}'.format(name,val_raw_dict[name]['value_cal']))                       

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
                raise ValueError('"{}" is not a valid timestamp format'.format(timestamp))

