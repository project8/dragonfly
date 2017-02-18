'''
A service fo interfacing with the DAQ DB (the run table in particular)

Note: services using this module will require sqlalchemy (and assuming we're still using postgresql, psycopg2 as the sqlalchemy backend)
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
from datetime import datetime
from itertools import groupby
import collections

# local imports
from dripline.core import Provider, Endpoint, fancy_doc, constants
from dripline.core.exceptions import *

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@fancy_doc
class PostgreSQLInterface(Provider):
    '''
    A not-so-flexible provider for getting run_id values.
    '''

    def __init__(self, database_name, database_server, metadata_target='', **kwargs):
        '''
        database_name (str): name of the database to connect to
        database_server (str): network resolvable hostname of database server
        metadata_target (str): target to send metadata to
        '''
        if not 'sqlalchemy' in globals():
            raise ImportError('SQLAlchemy not found, required for PostgreSQLInterface class')
        Provider.__init__(self, **kwargs)
        self._connect_to_db(database_server, database_name)
        self._metadata_target = metadata_target
        self._endpoint_name_set = set()

    def _connect_to_db(self, database_server, database_name):
        '''
        '''
        logger.debug('Connecting to the db')
        credentials = json.loads(open(os.path.expanduser('~')+'/.project8_authentications.json').read())['postgresql']
        engine_str = 'postgresql://{}:{}@{}/{}'.format(credentials['username'],
                                                       credentials['password'],
                                                       database_server,
                                                       database_name
                                                      )
        self.engine = sqlalchemy.create_engine(engine_str)
        self.meta = sqlalchemy.MetaData(self.engine)

    def add_endpoint(self, endpoint):
        Provider.add_endpoint(self, endpoint)
        if isinstance(endpoint, SQLTable):
            logger.debug('Adding endpoint {} to the table'.format(endpoint.table_name))
            endpoint.table = sqlalchemy.Table(endpoint.table_name, self.meta, autoload=True, schema=endpoint.schema)
        if isinstance(endpoint, SQLSnapshot):
            self._endpoint_name_set.update(endpoint.target_items)

    def take_snapshot(self, start_time, end_time, filename):
        run_snapshot = {}
        logger.info('doing logs-snapshot gets')
        for child in self.endpoints:
            snapshot_result = self.endpoints[child].get_logs(start_time,end_time)
            these_snaps = snapshot_result['value_raw']
            run_snapshot.update(these_snaps)
        logger.info('doing latest-snapshot gets')
        latest_snap = {}
        for child in self.endpoints:
            snapshot_result = self.endpoints[child].get_latest(start_time, self.endpoints[child].target_items)
            these_snaps = snapshot_result['value_raw']
            latest_snap.update(these_snaps)
        for latest_endpoint in latest_snap.keys():
            run_snapshot.setdefault(latest_endpoint,[]).append(latest_snap[latest_endpoint][0])
        for endpoint_name in sorted(run_snapshot.keys()):
            if not set([endpoint_name])<=self._endpoint_name_set:
                run_snapshot.pop(endpoint_name)
        logger.info('snapshot of the slow control database should broadcast')
        logger.debug('should request snapshot file: {}'.format(filename))
        this_payload = {'contents': run_snapshot,
                        'filename': filename}
        req_result = self.provider.cmd(self._metadata_target, None, payload=this_payload)
        logger.debug('snapshot sent')
        return


@fancy_doc
class SQLTable(Endpoint):
    '''
    A class for making calls to _insert_with_return
    '''
    def __init__(self, table_name, schema,
                 required_insert_names=None,
                 return_col_names=[],
                 optional_insert_names=[],
                 default_insert_values={},
                 *args,
                **kwargs):
        '''
        table_name (str): name of the table within the database
        schema (str): name of the schema where the table is located
        required_insert_names (list): list of names (str) of the table columns which must be included on every requested insert
        return_col_names (list): list of names (str) of columns whose values should be returned on completion of the insert
        optional_insert_names (list): list of names (str) of columns which the user may specify on an insert request, but which may be omitted
        default_insert_values (dict): dictionary of {column_names: values} to serve as defaults when inserting, any values provided explicitly on the insert request will override these values
        '''
        if not 'sqlalchemy' in globals():
            raise ImportError('SQLAlchemy not found, required for SQLTable class')
        Endpoint.__init__(self, *args, **kwargs)
        self.table = None
        self.table_name = table_name
        self.schema = schema
        self._return_names = return_col_names
        self._required_insert_names = required_insert_names
        self._optional_insert_names = optional_insert_names
        self._default_insert_dict = default_insert_values


    def do_select(self, return_cols=[], where_eq_dict={}, where_lt_dict={}, where_gt_dict={}):
        '''
        return_cols (list of str): string names of columns, internally converted to sql reference; if evaluates as false, all columns are returned
        where_eq_dict (dict): keys are column names (str), and values are tested with '=='
        where_lt_dict (dict): keys are column names (str), and values are tested with '<'
        where_gt_dict (dict): keys are column names (str), and values are tested with '>'

        Other select "where" statements are not supported

        Returns: a tuple, 1st element is list of column names, 2nd is a list of tuples of the rows that matched the select
        '''
        if not return_cols:
            return_cols = self.table.c
        else:
            return_cols = [sqlalchemy.text(col) for col in return_cols]
        this_select = sqlalchemy.select(return_cols)
        for c,v in where_eq_dict.items():
            this_select = this_select.where(getattr(self.table.c,c)==v)
        for c,v in where_lt_dict.items():
            this_select = this_select.where(getattr(self.table.c,c)<v)
        for c,v in where_gt_dict.items():
            this_select = this_select.where(getattr(self.table.c,c)>v)
        result = self.provider.engine.execute(this_select)
        return (result.keys(), [i for i in result])

    def _insert_with_return(self, insert_kv_dict, return_col_names_list):
        try:
            ins = self.table.insert().values(**insert_kv_dict)
            if return_col_names_list:
                ins = ins.returning(*[self.table.c[col_name] for col_name in return_col_names_list])
            insert_result = ins.execute()
            if return_col_names_list:
                return_values = insert_result.first()
            else:
                return_values = []
        except Exception as err:
            if str(err).startswith('(psycopg2.IntegrityError)'):
                raise DriplineDatabaseError(str(err))
            else:
                logger.critical('received an unexpected SQL error while trying to insert:\n{}'.format(str(ins) % insert_kv_dict))
                logger.info('traceback is:\n{}'.format(traceback.format_exc()))
                return
        return dict(zip(return_col_names_list, return_values))

    def do_insert(self, *args, **kwargs):
        '''
        '''
        if not isinstance(self.provider, PostgreSQLInterface):
            raise DriplineInternalError('InsertDBEndpoint must have a RunDBInterface as provider')
        # make sure that all provided insert values are expected
        for col in kwargs.keys():
            if (not col in self._required_insert_names) and (not col in self._optional_insert_names):
                #raise DriplineDatabaseError('not allowed to insert into: {}'.format(col))
                logger.warning('got an unexpected insert column <{}>'.format(col))
                kwargs.pop(col)
        # make sure that all required columns are present
        for col in self._required_insert_names:
            if not col in kwargs.keys():
                raise DriplineDatabaseError('a value for <{}> is required!\ngot: {}'.format(col, kwargs))
        # build the insert dict
        this_insert = self._default_insert_dict.copy()
        this_insert.update(kwargs)
        return_vals = self._insert_with_return(this_insert,
                                               self._return_names,
                                              )
        return return_vals

@fancy_doc
class SQLSnapshot(SQLTable):

    def __init__(self, table_name, schema, target_items=None, *args, **kwargs):
        '''
        target_items (list): items (str) to take snapshot of
        '''
        if not 'sqlalchemy' in globals():
            raise ImportError('SQLAlchemy not found, required for SQLSnapshot class')
        SQLTable.__init__(self, table_name, schema, *args, **kwargs)
        self.target_items = target_items

    def get_logs(self, start_timestamp, end_timestamp):
        '''
        Both inputs must be follow the format of constants.TIME_FORMAT, i.e. YYYY-MM-DDThh:mm:ssZ
        start_timestamp (str): oldest timestamp for query into database
        ending_timesamp (str): most recent timestamp for query into database
        '''
        start_timestamp = str(start_timestamp)
        end_timestamp = str(end_timestamp)

        # Parsing timestamps
        self._try_parsing_date(start_timestamp)
        self._try_parsing_date(end_timestamp)
        if not end_timestamp > start_timestamp:
            raise DriplineValueError('end_timestamp ("{}") must be > start_timestamp ("{}")!'.format(end_timestamp,start_timestamp))

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
        except DriplineDatabaseError as dripline_error:
            logger.error('{}; in executing SQLAlchemy select statement'.format(dripline_error.message))
            return
        if not query_return:
            logger.critical('no entries found in database between "{}" and "{}" hence producing empty snapshot'.format(start_timestamp,end_timestamp))

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
        val_dict = {'timestamp':None,'value_cal':None}
        val_raw_dict = {}
        val_cal_list = []
        index = 0
        for endpoint,times in endpoint_dict.items():
            val_raw_dict[endpoint] = []
            ept_timestamp_list = []
            for i in range(times):
                val_raw_dict[endpoint].append(val_dict.copy())
                query_row = query_return[index]
                val_raw_dict[endpoint][i]['timestamp'] = query_row['timestamp'].strftime(constants.TIME_FORMAT)
                val_raw_dict[endpoint][i]['value_cal'] = query_row['value_cal']
                ept_timestamp_list.append('{} {{{}}}'.format(val_raw_dict[endpoint][i]['value_cal'],val_raw_dict[endpoint][i]['timestamp']))
                index += 1
            ept_timestamp_results = ', '.join(ept_timestamp_list)
            val_cal_list.append('{} -> {}'.format(endpoint,ept_timestamp_results))

        return {'value_raw': val_raw_dict, 'value_cal': '\n'.join(val_cal_list)}


    def get_latest(self, timestamp, endpoint_list):
        '''
        timestamp (str): timestamp upper bound for selection. Format must follow constants.TIME_FORMAT, i.e. YYYY-MM-DDThh:mm:ssZ
        endpoint_list (list): list of endpoint names (str) of interest. Usage for dragonfly CLI e.g. endpoint_list='["endpoint_name1","endpoint_name_2",...]'
        '''
        timestamp = str(timestamp)
        if isinstance(endpoint_list,types.ListType):
            endpoint_list = [str(item) for item in endpoint_list]
        else:
            logger.error('Received type "{}" for argument endpoint_list instead of Python list'.format(type(endpoint_list).__name__))
            raise DriplineValueError('expecting a list but received type {}'.format(type(endpoint_list).__name__))

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
            except DriplineDatabaseError as dripline_error:
                logger.error('{}; in executing SQLAlchemy select statement to obtain endpoint_id for endpoint "{}"'.format(dripline_error.message,name))
                return
            if not query_return:
                logger.critical('endpoint with name "{}" not found in database hence failed to take snapshot of its value; might need to add it to the db'.format(name))
                continue
            else:
                ept_id = query_return[0]['endpoint_id']
            logger.debug('endpoint id "{}" matched to endpoint "{}"'.format(ept_id,name))
            s = sqlalchemy.select([t]).where(sqlalchemy.and_(t.c.endpoint_id == ept_id,t.c.timestamp < timestamp))
            s = s.order_by(t.c.timestamp.desc()).limit(1)
            try:
                query_return = self.provider.engine.execute(s).fetchall()
            except DriplineDatabaseError as dripline_error:
                logger.error('{}; in executing SQLAlchemy select statement for endpoint "{}"'.format(dripline_error.message,name))
                return
            if not query_return:
                logger.critical('no records found before "{}" for endpoint "{}" in database hence not recording its snapshot'.format(timestamp,name))
                continue
            else:
                val_raw_dict[name] = [{'timestamp' : query_return[0]['timestamp'].strftime(constants.TIME_FORMAT),
                                      'value_cal' : query_return[0]['value_cal']}]
                val_cal_list.append('{} -> {} {{{}}}'.format(name,val_raw_dict[name][0]['value_cal'],val_raw_dict[name][0]['timestamp']))

        return {'value_raw': val_raw_dict, 'value_cal': '\n'.join(val_cal_list)}


    def _try_parsing_date(self, timestamp):
        '''
        Checks if timestamp (str) is in correct format for database query
        '''
        try:
            return datetime.strptime(timestamp, constants.TIME_FORMAT)
        except ValueError:
            pass
        raise DriplineValueError('"{}" is not a valid timestamp format'.format(timestamp))


    def _connect_id_table(self):
        '''
        Connects to the 'endpoint_id_map' table in database
        '''
        try:
            self.it = sqlalchemy.Table('endpoint_id_map',self.provider.meta, autoload=True, schema=self.schema)
        except DriplineDatabaseError as dripline_error:
            logger.error('{}; when establishing connection to the "endpoint_id_map" table'.format(dripline_error.message))
