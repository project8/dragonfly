from dripline.core import ThrowReply, Service
from dripline.implementations import PostgreSQLInterface, SQLTable

import logging
logger = logging.getLogger(__name__)

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

    def get_snapshot(self):
        return {"test": "snapshot", "second": "entry"}
    
class SQLSnapshotEndpoint(SQLTable):
    '''
    Endpoint to get a snapshot of the current state of the device, as stored in a SQL table.
    '''
    def __init__(self, table_name, **kwargs):
        '''
        Args:
            table_name (str): name of the SQL table to query for snapshots.
        '''
        SQLTable.__init__(self, table_name=table_name, **kwargs)



        
