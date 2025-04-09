#!/user/bin/env python3
import requests
import json
import time
import docker
import dripline
import yaml
from pathlib import Path
import argparse

from dripline.core import Interface

class WatchDog(object):
    def __init__(self, config_path):
        self.config_path = config_path
        self.load_configuration()
        self.setup_docker_client()
        self.setup_dripline_connection()
        self.send_slack_message("Started alarm system!")

    def load_configuration(self):
        with open(Path(args.config), "r") as open_file:
            self.config = yaml.safe_load( open_file.read() )
        
        if not "slack_hook" in self.config.keys():
            self.config["slack_hook"] = None
        
        print("Configuration is:", flush=True)
        print(self.config, flush=True)

    def setup_docker_client(self):
        self.client = docker.from_env()

    def setup_dripline_connection(self):
        self.connection = Interface(username=self.config["dripline_username"], 
                                    password=self.config["dripline_password"], 
                                    dripline_mesh=self.config["dripline_mesh"])

    def send_slack_message(self, message):
        if self.config["slack_hook"] is None:
            print("Slack hook not configured. No message will be send!")
            return
        post = {"text": "{0}".format(message)}
        response = requests.post(self.config["slack_hook"], headers={'Content-Type': 'application/json'}, data=json.dumps(post))
                          
        if response.status_code != 200:
            print(f'Request to slack returned an error {response.status_code}, the response is:\n{response.text}')
            

    def get_endpoint(self, endpoint, calibrated=False):
        val = self.connection.get(endpoint)
        return val["value_raw" if not calibrated else "value_cal"]

    def compare(self, value, reference, method):
        if method == "not_equal":
            return value != reference
        elif method == "equal":
            return value == reference
        elif method == "lower":
            return value < reference
        elif method == "greater":
            return value > reference
        else:
            raise ValueError(f"Comparison method {method} is not defined. You can use one of ['not_equal', 'equal', 'lower', 'greater'].")

    def run(self):

        while True:
            for entry in self.config["check_endpoints"]:
                value = self.get_endpoint(entry["endpoint"])
                print(entry["endpoint"], value, flush=True)
                if self.compare(value, entry["reference"], "not_equal"):
                    self.send_slack_message(entry["message"].format(**locals()))

            for container in self.client.containers.list(all=True):
                if any([container.name.startswith(black) for black in self.config["blacklist_containers"]]):
                   continue
                if container.status != "running":
                    send_slack_message(f"Container {container.name} is not running!")
                if int(container.attrs["State"]["ExitCode"]) != 0:
                    send_slack_message(f"Containeri {container.name} has exit code {container.attrs['State']['ExitCode']}!")
        
            print("Checks done", flush=True)
            time.sleep(int(self.config["check_interval_s"]))


if __name__ == "__main__":
    print("Welcome to Watchdog", flush=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path of the yaml config file.")
    args = parser.parse_args()

    dog = WatchDog(args.config)
    dog.run()
