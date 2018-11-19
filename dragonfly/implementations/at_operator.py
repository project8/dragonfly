import datetime, logging, os, time, funcsigs, json
from dateutil import parser
# for google
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
# for slack
from slackclient import SlackClient

logger = logging.getLogger(__name__)
# need to export BOT_TOKEN first

class AtOperator():
    
    def __init__(self, directory = '/home/yadiw/Desktop/Operator/bot_token.json', monitor_channel_name = 'general'):

        self.calendar_scope = 'https://www.googleapis.com/auth/calendar.readonly'

        with open(directory, 'r') as load_f:
            token_dict = json.load(load_f)
            self.slack_client = SlackClient(token_dict["bot_token"])
            
        self.monitor_channel_name = monitor_channel_name
        self.monitor_channel_id = ''
        self.channel_name_to_id_dictionary = {}
        self.channel_id_to_name_dictionary = {}

        self.current_operator_name = ''
        self.current_operator_id = ''
        self.temporary_operator_id = []

        self.full_name_to_id_dictionary = {}
        self.id_to_username_dictionary = {}
        self.username_to_id_dictionary = {}

        self.command_dictionary = {}

    # get credentials from google calendar
    def get_credentials(self):
        creds_dir = os.path.join(os.path.expanduser('~'), '.credentials')
        if not os.path.exists(creds_dir):
            os.makedirs(creds_dir)
        creds_path = os.path.join(creds_dir, 'calendar-go-quickstart.json')
        store = file.Storage(creds_path)
        creds = store.get()
        if not creds or creds.invalid:
            flow = client.flow_from_clientsecrets('credentials.json', self.calendar_scope)
            creds = tools.run_flow(flow, store)
        return creds

    def get_event_list(self, creds):
        service = build('calendar', 'v3', http=creds.authorize(Http()))
        time= (datetime.datetime.now() - datetime.timedelta(hours=10)).isoformat() + 'Z'
        events_list = service.events().list(calendarId='primary', timeMin=time, 
                                            maxResults=100, singleEvents=True, 
                                            orderBy='startTime').execute()
        events = events_list.get('items', [])
        if not events:
            logger.warning(' No events found.')
        return events

    def get_event_time(self, event, start):
        point = 'start'
        if not start:
            point = 'end'
        if event[point].get('dateTime') != None:
            return parser.parse(event[point].get('dateTime')).replace(tzinfo=None)
        else:
            date = datetime.datetime.strptime(event[point].get('date'),'%Y-%m-%d')
            if start:
                return datetime.datetime.combine(date, datetime.datetime.min.time())
            else:
                return datetime.datetime.combine(date, datetime.datetime.max.time())
        
    def get_operator_name(self, events):
        for event in events:
            if 'Operator:' in event['summary']:
                time_now = datetime.datetime.now()
                if self.get_event_time(event, True) < time_now and self.get_event_time(event, False) > time_now:
                    return event['summary'].replace('Operator: ', '')
        return None

    def construct_user_dictionaries(self):
        request = self.slack_client.api_call("users.list")
        if request['ok']:
            full_name_to_id_dictionary = {}
            id_to_username_dictionary = {}
            username_to_id_dictionary = {}
            for m in request['members']:
                if not m['is_bot']:
                    full_name_to_id_dictionary[m['real_name']] = m['id']
                    id_to_username_dictionary[m['id']] = m['name']
                    username_to_id_dictionary[m['name']] = m['id']
            logger.info(' Constructed dictionaries for full names, Slack usernames and ids.')
            return full_name_to_id_dictionary, id_to_username_dictionary, username_to_id_dictionary
        else:
            return None, None, None
    
    def construct_channel_dictionaries(self):
        logger.info(" Trying to construct an dictionary mapping channel names to their ids.")
        request = self.slack_client.api_call("conversations.list")
        if request['ok']:
            channel_name_to_id_dictionary = {}
            channel_id_to_name_dictionary = {}
            for c in request['channels']:
                channel_name_to_id_dictionary[c['name']] = c['id']
                channel_id_to_name_dictionary[c['id']] = c['name']
            logger.info(' Constructed dictionaries containing information of ' + str(len(request['channels'])) + ' channels.')
            return channel_name_to_id_dictionary, channel_id_to_name_dictionary

        else:
            return None, None


    # send message to an channel where @operator or any helper command is called.
    def send_message(self, channel, text):
        if channel in self.channel_id_to_name_dictionary:
            self.slack_client.api_call("chat.postMessage", channel=channel, text=text, as_user=True)

    def at_operator(self, channel):
        self.send_message(channel, "Get it!")
        if len(self.temporary_operator_id) != 0:
            logger.info(' Found temporary operator(s)!')
            message = ""
            for operator_id in self.temporary_operator_id:
                message += "<@" + operator_id + "> "
            self.send_message(channel, message)
        elif self.current_operator_id == "":
            self.send_message(channel, 'No valid information of current operator is found')
        else:
            self.send_message(channel, "<@" + self.current_operator_id + ">")

        
    def command_hello(self, channel, user_id):
        self.send_message(channel, "Hi, " + self.id_to_username_dictionary[user_id] + ".")

    def command_help(self, channel):
        message = "You can either address me with `@operator` or enter a command.\n\n" + \
                  "If you address me with `@operator` I'll pass a notification on to the current operator.\n\n" + \
                  "I determine the current operator from the Operator entries in the Google calendar. If you need to make modifications to the current or future operator, please contact the operations coordinator.\n\n" + \
                  "If you enter a command, I can take certain actions:\n" + \
                  "\t`!hello`: say hi\n" + \
                  "\t`!help`: display this help message\n" + \
                  "\t`!whoisop`: show who the current operator is, plus any temporary operators\n" + \
                  "\t`!tempoperator [username (optional)]`: add yourself or someone else as a temporary operator; leave the username blank to add yourself\n" + \
                  "\t`!removetempoperator [username (optional)]`: remove yourself or someone else as temporary operator; leave the username blank to remove yourself"
        self.send_message(channel, message)
        
    def command_whoisop(self, channel):
        if self.current_operator_id == "" and len(self.temporary_operator_id) == 0:
            self.send_message(channel, "There is no operator assigned right now.")
        else:
            if self.current_operator_id != "":
                self.send_message(channel, "The operator is " + self.id_to_username_dictionary[self.current_operator_id] + "." )
            if len(self.temporary_operator_id) != 0:
                message = "Temporary operator(s): "
                for operator_id in self.temporary_operator_id:
                    message += self.id_to_username_dictionary[operator_id] + " "
                self.send_message(channel, message)
    
    def command_tempoperator(self, channel, user_id, operator_name = ""):
        if operator_name == "":
            self.temporary_operator_id.append(user_id)
            self.temporary_operator_id = list(set(self.temporary_operator_id))
            self.send_message(channel, "Use your powers wisely, " + self.id_to_username_dictionary[user_id] + ".")
        elif operator_name not in self.username_to_id_dictionary:
                self.send_message(channel, "Sorry, I don't recognize that username.")
        else:
            self.temporary_operator_id.append(self.username_to_id_dictionary[operator_name])
            self.send_message(channel, "Use your powers wisely, " + operator_name + '.')

    def command_removetempoperator(self, channel, user_id, operator_name = ""):
        remove = user_id
        if operator_name != "":
            if operator_name not in self.username_to_id_dictionary:
                self.send_message(channel, "Sorry, I don't rocognize that username.")
                return
            remove = self.username_to_id_dictionary[operator_name]
        if remove not in self.temporary_operator_id:
            self.send_message(channel, self.id_to_username_dictionary[remove] + "is not currently listed as a temporary operator.")
            return
        self.temporary_operator_id.remove(remove)
        self.send_message(channel, "Ok, you're all done. Thanks!")
            
    def construct_command_dictionary(self):
        self.command_dictionary["!hello"] = self.command_hello
        self.command_dictionary["!help"] = self.command_help
        self.command_dictionary["!whoisop"] = self.command_whoisop
        self.command_dictionary["!tempoperator"] = self.command_tempoperator
        self.command_dictionary["!removetempoperator"] = self.command_removetempoperator
        logger.info(' Constructed dictionaries for operator helper commands on Slack.')

    def parse_output(self, rtm_output, bot_id):
        output = rtm_output
        if output and len(output) > 0:
            for o in output:
                if o and 'text' in o:
                    if ('@' + str(bot_id)) in o['text']:
                        return o['channel']
                    tokens = o['text'].split(' ', 1)
                    command = tokens[0]

                    if command in self.command_dictionary:
                        logger.info(' A helper command [' + command + '] is called!')
                        channel = o["channel"]
                        user_id = o["user"]
                        operator_name = ""
                        if len(tokens) > 1 and tokens[1].startswith('[') and "]" in tokens[1]:
                            sub_tokens = tokens[1].split(']', 1)
                            operator_name = sub_tokens[0].replace('[', '')
                            logger.info(' Found a potential operator name [' + operator_name + '] !')
                        func = self.command_dictionary[command]
                        num_args = len(funcsigs.signature(func).parameters)
                        args = [channel, user_id, operator_name]
                        func(*args[:num_args])
        return None



    def run(self):
        logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
        if self.slack_client.rtm_connect():
            logger.info(' Connected!')
            bot_id = self.slack_client.api_call('auth.test')['user_id']
            if not bot_id:
                logger.critical(' Unable to get the bot user ID.')
                os.exit(1)
            logger.info(' Got Slack Operator bot id.')

            self.full_name_to_id_dictionary, self.id_to_username_dictionary, self.username_to_id_dictionary = self.construct_user_dictionaries()
            if not self.full_name_to_id_dictionary:
                logger.critical(" Cannot get the list of users.")
                os.exit(1)

            self.channel_name_to_id_dictionary, self.channel_id_to_name_dictionary = self.construct_channel_dictionaries()
            if not self.channel_name_to_id_dictionary:
                logger.error(' Cannot get the list of channels, therefore cannot find the monitor channel. Related functionalities will be disabled.')
            elif self.monitor_channel_name not in self.channel_name_to_id_dictionary:
                logger.error(' The name of monitor channel is not found. Related functionalities will be disabled.')
            else:
                self.monitor_channel_id = self.channel_name_to_id_dictionary[self.monitor_channel_name]
                logger.info(' The id for monitor channel [' + self.monitor_channel_name + '] is : ' + str(self.monitor_channel_id))

            self.construct_command_dictionary()
            self.send_message(self.monitor_channel_id, "Have no fear, @operator is here!")
            
            creds = self.get_credentials()
            events = self.get_event_list(creds)
            if not events:
                logger.critical(' Unable to get Google Calendar event list.')
                os.exit(1)
            logger.info(' Successfully get ' + str(len(events)) + ' events from Google Calendar.')
            update_time = datetime.datetime.now() + datetime.timedelta(minutes=30) 
            
            while True:
                channel = self.parse_output(self.slack_client.rtm_read(), bot_id)
                if datetime.datetime.now() > update_time:

                    # to-do: also update dictionaries and operator information

                    new_events = self.get_event_list(creds)
                    if not new_events:
                        logger.warning(' The update of Google Calendar event list fails. Information might be outdated.')
                    else:
                        events = new_events
                        logger.info(' Successfully updated the Google Calendar event list. Next update will occur 30 minutes later.')
                    update_time = datetime.datetime.now() + datetime.timedelta(minutes=30)
                if channel:
                    logger.info(' @operator is called in the channel [' + str(channel) + ']! Looking for the operator...')
                    new_operator_name = self.get_operator_name(events)
                    if not new_operator_name:
                        self.current_operator_name = ""
                        self.current_operator_id = ""
                        logger.info(' No current operator found in Google Calendar.')
                    elif new_operator_name not in self.full_name_to_id_dictionary:
                        self.current_operator_name = ""
                        self.current_operator_id = ""
                        valid_operator = False
                        logger.warning(' The operator listed in Google Calendar is not found in Slack!')
                    elif new_operator_name != self.current_operator_name:
                        self.current_operator_name = new_operator_name
                        self.current_operator_id = self.full_name_to_id_dictionary[self.current_operator_name]
                        logger.info(' Found a new operator!')
                    self.at_operator(channel)
                            

                time.sleep(1)
        else:
            logger.critical(" An error occurs when connecting to Slack.")
            os.exit(1)



if __name__ == '__main__':
    logging.basicConfig()
    logger.setLevel("INFO")
    o = AtOperator()
    o.run()
