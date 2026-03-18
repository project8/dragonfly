from dripline.core import ThrowReply, Service
from dripline.implementations import PostgreSQLInterface, SQLTable



# std libraries
import json
import os
import types

# 3rd part libraries
try:
    import sqlalchemy
except ImportError:
    pass
from datetime import datetime
from itertools import groupby
import collections

import logging
logger = logging.getLogger(__name__)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

__all__ = []

__all__.append('SQLSnapshotService')

class SQLSnapshotService(Service, PostgreSQLInterface):

    def __init__(self, **kwargs):
        '''
        Args:
            database_name (str): name of the database to connect to.
            database_server (str): hostname of the database server to connect to.
            auth (dict): authentication credentials for the database.

        '''

        Service.__init__(self, add_endpoints_now=False, **kwargs)
        PostgreSQLInterface.__init__(self, **kwargs)
        self.connect_to_db(self.auth)
        self.add_endpoints_from_config()


    def take_snapshot(self, start_time, end_time, metadata_target, filename):
        run_snapshot = {}
        logger.info('doing logs-snapshot gets')
        for child in self.endpoints:
            logger.info(f'performing logs snapshot for {child}')
            snapshot_result = self.endpoints[child].get_logs(start_time,end_time)
            run_snapshot.update(snapshot_result['value_raw'])
        if run_snapshot == {}:
            logger.critical(f'No entries found in database between "{start_time}" and "{end_time}" hence producing empty snapshot')
        logger.info('doing latest-snapshot gets')
        latest_snap = {}
        for child in self.endpoints:
            snapshot_result = self.endpoints[child].get_latest(start_time, self.endpoints[child].target_items)
            latest_snap.update(snapshot_result)
        for latest_endpoint in latest_snap.keys():
            run_snapshot.setdefault(latest_endpoint,[]).append(latest_snap[latest_endpoint][0])
        for endpoint_name in sorted(run_snapshot.keys()):
            if not set([endpoint_name])<=self._endpoint_name_set:
                run_snapshot.pop(endpoint_name)
        logger.info('snapshot of the slow control database should broadcast')
        logger.debug(f'should request snapshot file: {filename}')
        this_payload = {'contents': run_snapshot,
                        'filename': filename}
        self.cmd(metadata_target, 'write_json', payload=this_payload)
        logger.debug('snapshot sent')
        return
    
    # Overrides Service.add_child. Needs to call both, one adds endpoint to service childrem, other adds table to endpoint. 
    def add_child(self, endpoint):
        Service.add_child(self, endpoint)
        PostgreSQLInterface.add_child_table(self, endpoint)
    
__all__.append('SQLSnapshotEndpoint')

class SQLSnapshotEndpoint(SQLTable):
    '''
    Endpoint to get a snapshot of the current state of the device, as stored in a SQL table.
    '''
    def __init__(self, target_items, payload_field='value_cal', *args, **kwargs):
        '''
        target_items (list): items (str) to take snapshot of
        payload_field (str): field to take from database instead of value_cal
        '''
        if not 'sqlalchemy' in globals():
            raise ImportError('SQLAlchemy not found, required for SQLSnapshot class')
        SQLTable.__init__(self, *args, **kwargs)
        self.target_items = target_items
        self.payload_field = payload_field

    def get_logs(self, start_timestamp, end_timestamp):
        '''
        Method to retrieve all database values for all endpoints between two timestamps.  Used as part of standard DAQ operation
        Both input timestamps must be follow the format of TIME_FORMAT, i.e. YYYY-MM-DDThh:mm:ssZ
        start_timestamp (str): oldest timestamp for query into database
        ending_timesamp (str): most recent timestamp for query into database
        '''
        start_timestamp = str(start_timestamp)
        end_timestamp = str(end_timestamp)

        # Parsing timestamps
        self._try_parsing_date(start_timestamp)
        self._try_parsing_date(end_timestamp)
        if not end_timestamp > start_timestamp:
            raise ThrowReply("ServiceError", f'end_timestamp ("{end_timestamp}") must be > start_timestamp ("{start_timestamp}")!')

        # Connect to id map table + assign alises
        self._connect_id_table()
        t = self.table.alias()

        # Select query + result
        s = sqlalchemy.select(t.c.endpoint_name,t.c.timestamp,t.c.value_raw,t.c.value_cal)
        logger.debug(f'querying database for entries between "{start_timestamp}" and "{end_timestamp}"')
        s = s.where(sqlalchemy.and_(t.c.timestamp>=start_timestamp,t.c.timestamp<=end_timestamp)).order_by(t.c.endpoint_name.asc())
        try:
            with self.service.engine.connect() as conn:
                query_return = conn.execute(s).fetchall()
        except Exception as error:
            logger.error(f'{error}; in executing SQLAlchemy select statement')
            raise ThrowReply("ServiceError", 'Unable to execute database query for logs snapshot')
        if not query_return:
            logger.info('returning empty record')
            return {'value_raw': {}}
        logger.debug(f'query return for logs snapshot is {query_return[0]} ... {query_return[-1]}')

        # Counting how many times each endpoint is present
        endpoint_name_raw = []
        endpoint_dict = {}
        for row in query_return:
            endpoint_name_raw.append(str(row._asdict()['endpoint_name']))
        for key,group in groupby(endpoint_name_raw):
            endpoint_dict[key] = len(list(group))
        # Ordering according to SQL query return
        endpoint_dict = collections.OrderedDict(sorted(endpoint_dict.items(),key=lambda pair:pair[0].lower()))

        # Parsing result
        val_dict = {'timestamp':None,self.payload_field:None}
        val_raw_dict = {}
        val_cal_list = []
        index = 0
        logger.debug(f'Database log query return for endpoints {list(endpoint_dict.keys())}')
        for endpoint,times in endpoint_dict.items():
            val_raw_dict[endpoint] = []
            ept_timestamp_list = []
            for i in range(times):
                val_raw_dict[endpoint].append(val_dict.copy())
                query_row = query_return[index]
                val_raw_dict[endpoint][i]['timestamp'] = query_row._asdict()['timestamp'].strftime(TIME_FORMAT)
                val_raw_dict[endpoint][i][self.payload_field] = query_row._asdict()[self.payload_field]
                ept_timestamp_list.append(f'{val_raw_dict[endpoint][i][self.payload_field]} {{{val_raw_dict[endpoint][i]["timestamp"]}}}')
                index += 1
            ept_timestamp_results = ', '.join(ept_timestamp_list)
            val_cal_list.append(f'{endpoint} -> {ept_timestamp_results}')

        return {'value_raw': val_raw_dict, 'value_cal': '\n'.join(val_cal_list)}


    def get_single_log(self, start_timestamp, end_timestamp, *args):
        '''
        Method to retrieve all database values for subset of endpoints between two timestamps.
        Both input timestamps must be follow the format of TIME_FORMAT, i.e. YYYY-MM-DDThh:mm:ssZ
        start_timestamp (str): oldest timestamp for query into database
        ending_timesamp (str): most recent timestamp for query into database
        *args: list of endpoints of interest
        '''
        start_timestamp = str(start_timestamp)
        end_timestamp = str(end_timestamp)
        if len(args) == 0:
            raise ThrowReply("ServiceError", 'requires at least one endpoint arg provided')

        # Parsing timestamps
        self._try_parsing_date(start_timestamp)
        self._try_parsing_date(end_timestamp)
        if not end_timestamp > start_timestamp:
            raise ThrowReply("ServiceError", f'end_timestamp ("{end_timestamp}") must be > start_timestamp ("{start_timestamp}")!')

        # Connect to id map table + assign alises
        self._connect_id_table()
        t = self.table.alias()

        outdict = {}
        for endpoint in args:
            # Select query + result
            logger.debug(f'querying database for endpoint "{endpoint}" entries between "{start_timestamp}" and "{end_timestamp}"')
            s = sqlalchemy.select(t).where(sqlalchemy.and_(t.c.endpoint_name == endpoint,t.c.timestamp>start_timestamp,t.c.timestamp<end_timestamp)).order_by(t.c.timestamp.asc())
            try:
                with self.service.engine.connect() as conn:
                    query_return = conn.execute(s).fetchall()
            except Exception as error:
                logger.error(f'{error}; in executing SQLAlchemy select statement')
                raise ThrowReply("ServiceError", 'Unable to execute database query for logs snapshot')
            if not query_return:
                logger.warning(f'no entries found between "{start_timestamp}" and "{end_timestamp}"')

            outdict[endpoint] = [[entry._asdict()['timestamp'].strftime(TIME_FORMAT),entry._asdict()['value_cal'],entry._asdict()['value_raw']]for entry in query_return]

        with open(os.path.expanduser('~')+'/sqldump.txt','w') as fp:
            json.dump(obj=outdict,fp=fp)

        return {'value_raw': True, 'value_cal': "Files written to ~/sqldump.txt"}


    def get_latest(self, timestamp, endpoint):
        '''
        Method to retrieve last database value for all endpoints in list.  Used as part of standard DAQ operation
        timestamp (str): timestamp upper bound for selection. Format must follow TIME_FORMAT, i.e. YYYY-MM-DDThh:mm:ssZ
        endpoint (str): name of endpoint of interest. Usage for dragonfly CLI e.g. endpoint='endpoint_name1'
        '''
        timestamp = str(timestamp)
        if not isinstance(endpoint, str):
            logger.error(f'Received type "{type(endpoint).__name__}" for argument endpoint instead of Python str')
            raise ThrowReply("ServiceError", f'expecting a str but received type {type(endpoint).__name__}')

        # Parsing timestamp
        self._try_parsing_date(timestamp)

        # Connect to id map table + assign alises
        self._connect_id_table()
        t = self.table.alias()
        logger.debug(f"table cols are {t.c.keys()}")

        # Select query + result

        ept_id = self._get_endpoint_id(endpoint)

        s = sqlalchemy.select(t).where(sqlalchemy.and_(t.c.endpoint_name == endpoint,t.c.timestamp < timestamp))
        s = s.order_by(t.c.timestamp.desc()).limit(1)
        try:
            with self.service.engine.connect() as conn:
                query_return = conn.execute(s).fetchall()
        except Exception as dripline_error:
            logger.error(f'{Exception}; in executing SQLAlchemy select statement for endpoint "{endpoint}"')
            raise ThrowReply("ServiceError", f'Unable to execute database query for endpoint "{endpoint}"')
        logger.debug(f'query return for endpoint "{endpoint}" is {query_return}')
        if not query_return:
            logger.critical(f'no records found before "{timestamp}" for endpoint "{endpoint}" in database hence not recording its snapshot')
        else:
            val_dict = {'timestamp' : query_return[0]._asdict()['timestamp'].strftime(TIME_FORMAT),
                                    self.payload_field : query_return[0]._asdict()[self.payload_field]}
        return val_dict


    def _try_parsing_date(self, timestamp):
        '''
        Checks if timestamp (str) is in correct format for database query
        '''
        logger.debug(f'checking if timestamp "{timestamp}" is in correct format for database query')
        try:
            return datetime.strptime(timestamp, TIME_FORMAT)
        except ValueError:
            raise ThrowReply("ServiceError", f'"${timestamp}" is not a valid timestamp format, use "YYYY-MM-DDThh:mm:ssZ"')


    def _connect_id_table(self):
        '''
        Connects to the 'endpoint_id_map' table in database
        '''
        logger.debug('Attempting to establish connection to database id table "endpoint_id_map"')
        try:
            self.it = sqlalchemy.Table('endpoint_id_map',self.service.meta, autoload_with=self.service.engine, schema=self.schema)
        except Exception as error:
            logger.error(f'{error}; when establishing connection to the "endpoint_id_map" table')
            raise ThrowReply("ServiceError", 'Unable to connect to database id table "endpoint_id_map"')

    def _get_endpoint_id(self, endpoint):
        '''
        Queries database to match endpoint to endpoint id
        '''
        logger.debug(f'Attempting to match endpoint "{endpoint}" to endpoint id in database')
        id_table = self.it.alias()
        s = sqlalchemy.select(id_table.c.endpoint_id).where(id_table.c.endpoint_name == endpoint)
        with self.service.engine.connect() as conn:
            query_return = conn.execute(s).fetchall()
        logger.debug(f'query return for endpoint "{endpoint}" is {query_return}')
        if not query_return:
            raise ThrowReply("ServiceError", f"Endpoint with name '{endpoint}' not found in database")
        ept_id = query_return[0]._asdict()['endpoint_id']
        logger.debug(f"Endpoint id '{ept_id}' matched to endpoint '{endpoint}'")
        return ept_id



        
