'''
expanded monitoring of sensors
'''

from __future__ import absolute_import

'''
Notes:
'''



# standard libs
import logging
import re
import yaml
import os
from time import time

# internal imports
from dripline.core import Gogol, exceptions
#from .postgres_interface import PostgreSQLInterface

__all__ = []
logger = logging.getLogger(__name__)


__all__.append('expanded_monitor')
class expanded_monitor(Gogol):
    def __init__(self,sensor_definitions='', **kwargs):
        '''
        sensor_definition_file (str): name of a yaml file encoding sensor metadata
        '''
        Gogol.__init__(self, **kwargs)
#self.sensor_defs=yaml.load(open(os.path.expanduser(sensor_definition_file)))
        self.sensor_defs=sensor_definitions
        self.sensor_tags=dict()
        #use the sensor_types info to populate the sensor_tags
        for sensor_name in self.sensor_defs["sensors"]:
            for sensor_type in self.sensor_defs["sensors"][sensor_name]["sensor_types"]:
                if sensor_type in self.sensor_defs["sensor_types"]:
                    if "tag_conditions" in self.sensor_defs["sensors"][sensor_name]:
                        self.sensor_defs["sensors"][sensor_name]["tag_conditions"].extend(self.sensor_defs["sensor_types"][sensor_type]["tag_conditions"])
                    else:
                        self.sensor_defs["sensors"][sensor_name]["tag_conditions"]=self.sensor_defs["sensor_types"][sensor_type]["tag_conditions"]
                else:
                    logger.info("Error, sensor_type not found")
         #use the generic reactions to populate sensor reactions
        for sensor_name in self.sensor_defs["sensors"]:
            if "reactions" in self.sensor_defs["sensors"][sensor_name]:
                self.sensor_defs["sensors"][sensor_name]["reactions"].extend(self.sensor_defs["generic_reactions"])
            else:
                self.sensor_defs["sensors"][sensor_name]["reactions"]=self.sensor_defs["generic_reactions"]
        #the message queue is what I'm about to log to info
        #it's there so when I do things like email someone or post to slack,
        #I don't senda  whole bunch of messages. I only send the queue every queue_flush_time
        self.message_queue_info=""
        self.queue_flush_time_seconds=20
        self.last_queue_flush=time()-self.queue_flush_time_seconds

    def this_consume(self, message, basic_deliver):
        ### Get the sensor name
        sensor_name = None
        if '.' in basic_deliver.routing_key:
            re_out = re.match(r'sensor_value.(?P<from>\S+)', basic_deliver.routing_key)
            sensor_name = re_out.groupdict()['from']
        # note that the following is deprecated in dripline 2.x, retained for compatibility
        else:
            raise exceptions.DriplineValueError('unknown sensor name')
        
        #-----For this particular sensor, compare the value with the range for certain tags
        #-----If that value is within range, those tags are true
        logger.info("Relevant sensor name "+sensor_name)
        if sensor_name in self.sensor_defs["sensors"]:
            my_tags=[]
            if "tag_conditions" in self.sensor_defs["sensors"][sensor_name]:
                logger.info("investigating tag conditions for "+sensor_name)
                for cond in self.sensor_defs["sensors"][sensor_name]["tag_conditions"]:
                    value=0
                    if cond["raw_or_cal"] =="raw":
                        value=message.payload['value_raw'] 
                    else:
                        if not ( 'value_cal' in message.payload ):
                            continue
                        value=message.payload['value_cal'] 
                    #convert everything to a float just in case
                    r1=cond["range"][0]
                    r2=cond["range"][1]
                    if cond["value_type"] =="float":
                        value=float(value)
                        r1=float(r1)
                        r2=float(r2)
                    logger.info("for this condition, "+cond["raw_or_cal"]+" r1 is "+str(r1)+" and r2 is "+str(r2))
                    #if the value is within the range, the tags are true 
                    if r1 < value and r2 > value:
                        my_tags.extend(cond["tags"])
                        logger.info("conditioned satisfied, it gets the tag "+str(cond["tags"]))
            #--flag sensor as changed if tags have changed
            #--then resend if necessary
            if (not (sensor_name in self.sensor_tags)) or self.sensor_tags[sensor_name]!=my_tags:
                self.sensor_tags[sensor_name]=my_tags
                if "reactions" in self.sensor_defs["sensors"][sensor_name]:
                    for condition in self.sensor_defs["sensors"][sensor_name]["reactions"]:
                        if condition["stimulus"]=="hastag":
                            if condition["hastag"] in my_tags:
                                self.process_responses( condition["response"],{'sensor':sensor_name} )
            #flush the message queue
            if time()>self.last_queue_flush+self.queue_flush_time_seconds and self.message_queue_info!="":
                logger.critical(self.message_queue_info)
                self.last_queue_flush=time()
                self.message_queue_info=""

            
    def process_responses(self,responses,variables):
        for response in responses:
            if response["actiontype"]=="say":
                mymessage=response["message"]
                for key,value in variables.iteritems():
                    mymessage=mymessage.replace("$"+key,value)
                self.message_queue_info+=mymessage+"\n"
