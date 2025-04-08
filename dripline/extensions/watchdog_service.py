import time
import json
import requests
import docker
from datetime import datetime, timedelta
from enum import Enum
from dripline.core import ThrowReply
from dripline.implementations import HeartbeatMonitor, HeartbeatTracker

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('WatchDogTracker')
class WatchDogTracker(HeartbeatTracker):
    '''
    '''
    def __init__(self, **kwargs):
        '''
        '''
        HeartbeatTracker.__init__(self, **kwargs)

    def process_heartbeat(self, timestamp):
        '''
        '''
        logger.debug(f'New timestamp for {self.name}: {timestamp}')
        dt = datetime.fromisoformat(timestamp)
        posix_time = dt.timestamp()
        logger.debug(f'Time since epoch: {posix_time}')
        self.last_timestamp = posix_time

    def check_delay(self):
        '''
        '''
        diff = time.time() - self.last_timestamp
        if self.is_active:
            if diff > self.service.critical_threshold_s:
                # report critical
                logger.critical(f'Missing heartbeat: {self.name}')
                self.status = HeartbeatTracker.Status.CRITICAL
            else:
                if diff > self.service.warning_threshold_s:
                    # report warning
                    logger.warning(f'Missing heartbeat: {self.name}')
                    self.status = HeartbeatTracker.Status.WARNING
                else:
                    logger.debug(f'Heartbeat status ok: {self.name}')
                    self.status = HeartbeatTracker.Status.OK
        else:
            # report inactive heartbeat received
            logger.debug(f'Inactive heartbeat: time difference: {diff}')
            self.status = HeartbeatTracker.Status.UNKNOWN
        return {'status': self.status, 'time_since_last_hb': diff}

    class Status(Enum):
        OK = 0
        WARNING = 1
        CRITICAL = 2
        UNKNOWN = -1



__all__.append('WatchDogService')
class WatchDogService(HeartbeatMonitor):
    '''
    An alert consumer which listens to heartbeat messages and keeps track of the time since the last was received

    '''
    def __init__(self, **kwargs):
        '''
        Args:
            time_between_checks_s (int): number of seconds between heartbeat status checks
            warning_threshold_s (int): warning threshold for missing heartbeats (in seconds)
            critical_threshold_s (int): critical threshold for missing heartbeats (in seconds)
            add_unknown_heartbeats (bool): whether or not to add a new endpoint if an unknown heartbeat is received
            socket_timeout (int): number of seconds to wait for a reply from the device before timeout.
        '''
        self.slack_hook = kwargs.pop("slack_hook", None)
        self.blacklist = kwargs.pop("blacklist_containers", [])
        HeartbeatMonitor.__init__(self, **kwargs)
        self.slack_message("Started alert script")
        self.client = docker.from_env()

    def slack_message(self, text):
        if self.slack_hook is not None:
            post = {"text": "{0}".format(text)}
            response = requests.post(self.slack_hook, headers={'Content-Type': 'application/json'}, data=json.dumps(post))

            if response.status_code != 200:
                logger.error('Request to slack returned an error %s, the response is:\n%s' % (response.status_code, response.text) )

    def check_docker(self):
        for container in self.client.containers.list(all=True):
            if any([v in container.name for v in self.blacklist]):
                logger.info(f"Skip container {container.name} as it is in blacklist")
                continue
            if container.status != "running":
                logger.info(f"Container {container.name} is not running.")
                self.slack_message(f"Container {container.name} is not running.")
            if container.attrs["State"]["ExitCode"] != 0:
                self.slack_message(f"Container {container.name} has exit code {container.attrs['State']['ExitCode']}")
            if container.attrs["State"]["Error"] != "":
                self.slack_message(f"Container {container.name} has error {container.attrs['State']['Error']}")

    def run_checks(self):
        '''
        Checks all endpoints and collects endpoint names by heartbeat tracker status.
        '''
        self.check_docker()
        report_data = {
            HeartbeatTracker.Status.OK: [], 
            HeartbeatTracker.Status.WARNING: [], 
            HeartbeatTracker.Status.CRITICAL: [], 
            HeartbeatTracker.Status.UNKNOWN: [],
        }
        for an_endpoint in self.sync_children.values():
            try:
                endpoint_report = an_endpoint.check_delay()
                report_data[endpoint_report['status']].append(
                    {
                    'name': an_endpoint.name, 
                    'time_since_last_hb': endpoint_report['time_since_last_hb'],
                    }
                )
            except Exception as err:
                logger.error(f'Unable to get status of endpoint {an_endpoint.name}: {err}')
        return report_data
    
    def process_report(self, report_data):
        '''
        Print out the information from the monitoring report data.

        This function can be overridden to handle the monitoring report differently.
        '''
        logger.info('Heartbeat Monitor Status Check')
        if report_data[HeartbeatTracker.Status.CRITICAL]:
            logger.error('Services with CRITICAL status:')
            for endpoint_data in report_data[HeartbeatTracker.Status.CRITICAL]:
                logger.error(f'\t{endpoint_data['name']} -- TSLH: {timedelta(seconds=endpoint_data['time_since_last_hb'])}')
        if report_data[HeartbeatTracker.Status.WARNING]:
            logger.warning('Services with WARNING status:')
            for endpoint_data in report_data[HeartbeatTracker.Status.WARNING]:
                logger.warning(f'\t{endpoint_data['name']} -- TSLH: {timedelta(seconds=endpoint_data['time_since_last_hb'])}')
        if report_data[HeartbeatTracker.Status.OK]:
            logger.info(f'Services with OK status:')
            for endpoint_data in report_data[HeartbeatTracker.Status.OK]:
                logger.info(f'\t{endpoint_data['name']} -- TSLH: {timedelta(seconds=endpoint_data['time_since_last_hb'])}')
        if report_data[HeartbeatTracker.Status.UNKNOWN]:
            logger.info(f'Services with UNKNOWN status:')
            for endpoint_data in report_data[HeartbeatTracker.Status.UNKNOWN]:
                logger.info(f'\t{endpoint_data['name']} -- TSLH: {timedelta(seconds=endpoint_data['time_since_last_hb'])}')
