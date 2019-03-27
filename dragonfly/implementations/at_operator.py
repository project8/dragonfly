from __future__ import absolute_import

try:
    import dateutil, funcsigs
    # for google
    import googleapiclient.discovery
    from google.oauth2.credentials import Credentials
    import slackclient
except ImportError:
    pass

import datetime, logging, os, time, json

from dripline.core import Endpoint, fancy_doc
from .subprocess_mixin import SlowSubprocessMixin

__all__ = []
__all__.append('AtOperator')

logger = logging.getLogger(__name__)

@fancy_doc
class AtOperator(SlowSubprocessMixin, Endpoint):

    def __init__(self,
                 monitor_channel_name = 'slack_test',
                 update_interval = {"hours":12},
                 ping_interval = {"seconds":30},
                 authentication_path = ".project8_authentications.json",
                 **kwargs):
        '''
        monitor_channel_name: the name of Slack monitor channel.
        update_interval     : the time interval between regular checks and updates.
        authentication_path : the absolute path of the file that stores the authentication info.
        '''
        imports = ['dateutil', 'funcsigs', 'googleapiclient', 'Credentials', 'slackclient']
        for import_module in imports:
            if not import_module in globals():
                raise ImportError(import_module + ' not found, required for AtOperator class.')

        this_home = os.path.expanduser('~')
        self.authentication_path = os.path.join(this_home, authentication_path)
        try:
            json.loads(open(self.authentication_path).read())
        except IOError, err:
            logger.critical('The provided authentication file does not exist')
            os._exit(1)
        except ValueError, err:
            logger.critical('The provided authentication file is invalid.')
            os._exit(1)

        self.slack_client = None
        self.bot_id = None

        self._creds = None

        self.monitor_channel_name = monitor_channel_name
        self.monitor_channel_id = ''
        self.channel_name_to_id_dictionary = {}
        self.channel_id_to_name_dictionary = {}

        self.current_operator_name = ''
        self.current_operator_id = ''
        self.current_shift_end_time = datetime.datetime.now()
        self.next_shift_start_time = None

        self.temporary_operator_id = []

        self.full_name_to_id_dictionary = {}
        self.id_to_username_dictionary = {}
        self.username_to_id_dictionary = {}

        self.command_dictionary = {}

        self.update_interval = datetime.timedelta(**update_interval)
        self.ping_interval = datetime.timedelta(**ping_interval)
        
        Endpoint.__init__(self, **kwargs)
        SlowSubprocessMixin.__init__(self, self.run)

    def get_slack_client(self):
        '''
        Set up the slack client.
        '''
        slack = ''
        config_file = json.loads(open(self.authentication_path).read())
        if 'slack' in config_file and 'operator' in config_file['slack']:
            slack = config_file['slack']['operator']
            self.slack_client = slackclient.SlackClient(slack)
        else:
            logger.critical('Unable to find slack credentials for operator bot in {}'.format(self.authentication_path))
            os._exit(1)

    def get_calendar_credentials(self):
        '''
        Return google calendar credentials.
        '''
        creds_data = {}
        config_file = json.loads(open(self.authentication_path).read())
        if 'google' in config_file and 'calendar_credentials' in config_file['google']:
            creds_data = config_file['google']['calendar_credentials']
        try:
            return Credentials(**creds_data)
        except Exception:
            logger.critical('The Google calendar credentials does not exist or is invalid.')
            os._exit(1)

    def get_event_list(self, creds):
        '''
        Return a list of events found from the given calendar.
        creds: google calendar credentials.
        '''
        service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
        time= (datetime.datetime.now() - datetime.timedelta(hours=10)).isoformat() + 'Z'
        events_list = service.events().list(calendarId='primary', timeMin=time,
                                            maxResults=100, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_list.get('items', [])
        return events


    def get_event_time(self, event, start):
        '''
        Return the start/end time of a given event, without the timezone info.
        event: a single event retrieved from google calendar
        start: True if looking for start time, False if looking for end time
        '''
        point = 'start'
        if not start:
            point = 'end'
        if event[point].get('dateTime') != None:
            return dateutil.parser.parse(event[point].get('dateTime')).replace(tzinfo=None)
        else:
            date = datetime.datetime.strptime(event[point].get('date'),'%Y-%m-%d')
            return datetime.datetime.combine(date, datetime.datetime.min.time()) + datetime.timedelta(hours=9)

    def get_operator_name_and_time(self, events):
        '''
        Return the name of current operator, the time when his/her shift ends, and the time when the next shift begins.
        events: a list of events found from google calendar
        '''
        current_operator_name = None
        current_shift_end_time = None
        next_shift_start_time = None
        for event in events:
            if 'Operator:' in event['summary']:
                time_now = datetime.datetime.now()
                start_time = self.get_event_time(event, True)
                end_time = self.get_event_time(event, False)
                if not current_operator_name and start_time < time_now and end_time > time_now:
                    current_operator_name =  event['summary'].replace('Operator: ', '')
                    current_shift_end_time = end_time
                elif start_time > time_now:
                    next_shift_start_time = start_time
                    break
        return current_operator_name, current_shift_end_time, next_shift_start_time

    def send_message(self, channel, text):
        '''
        Send a given message to a given Slack channel if the channel exists.
        channel: Slack channel id
        text   : a string to be sent
        '''
        if channel in self.channel_id_to_name_dictionary:
            self.slack_client.api_call("chat.postMessage", channel=channel, text=text, as_user=True)

    def check_operator_validity(self, new_operator_name, shift_end_time, initial, regular_check):
        '''
        Check whether nor not the given new operator name is valid. If so, update information for current operator.
        new_operator_name: the full name of the new operator
        shift_end_time   : the end time corresponding to this operator
        initial          : True when called the first time, False otherwise
        regular_check    : True when called during a regular check, False otherwise
        '''
        message = ''
        if not new_operator_name:
            self.current_operator_name = ""
            self.current_operator_id = ""
            self.current_shift_end_time = datetime.datetime.now() + self.update_interval + datetime.timedelta(hours=1)
            logger.info('No current operator found in Google Calendar.')
            if not initial:
                message = 'The last operator has ended their shift: Good job!\n'
            message += 'No new operator found.'
        elif new_operator_name not in self.full_name_to_id_dictionary:
            self.current_operator_name = ""
            self.current_operator_id = ""
            self.current_shift_end_time = datetime.datetime.now() + self.update_interval + datetime.timedelta(hours=1)
            logger.warning('The operator listed in Google Calendar (' + new_operator_name + ') is not found in Slack!')
            message = 'The operator listed in Google Calendar is not found in Slack.'
        elif new_operator_name != self.current_operator_name:
            self.current_operator_name = new_operator_name
            self.current_operator_id = self.full_name_to_id_dictionary[self.current_operator_name]
            self.current_shift_end_time = shift_end_time
            logger.info('Found a new operator: ' + new_operator_name)
            self.send_message(self.monitor_channel_id, "I've found a new operator: " + new_operator_name + ". The shift will end at " + str(shift_end_time))
        elif shift_end_time > self.current_shift_end_time:
            self.current_shift_end_time = shift_end_time
            logger.info('Extended the shift time for current operator!')
            message = "It seems that the shift for current operator is extended! \n"
            message += "I'm not sure whether this branch will be used though."
        if not regular_check:
            self.send_message(self.monitor_channel_id, message)

    def construct_user_dictionaries(self):
        '''
        Return 3 dictionaries storing information of Slack users: full name to id, id to username, and username to id.
        '''
        request = self.slack_client.api_call("users.list")
        if request['ok']:
            full_name_to_id_dictionary = {}
            id_to_username_dictionary = {}
            username_to_id_dictionary = {}
            for m in request['members']:
                if not m['is_bot'] and not m['deleted']:
                    full_name_to_id_dictionary[m['real_name']] = m['id']
                    id_to_username_dictionary[m['id']] = m['name']
                    username_to_id_dictionary[m['name']] = m['id']
            logger.info('Constructed dictionaries for full names, Slack usernames and ids.')
            return full_name_to_id_dictionary, id_to_username_dictionary, username_to_id_dictionary
        else:
            return None, None, None

    def construct_channel_dictionaries(self):
        '''
        Return 2 dictionaries storing information of Slack channels: channel name to id, and channel id to name.
        '''
        logger.info("Trying to construct an dictionary mapping channel names to their ids.")
        request = self.slack_client.api_call("conversations.list")
        if request['ok']:
            channel_name_to_id_dictionary = {}
            channel_id_to_name_dictionary = {}
            for c in request['channels']:
                channel_name_to_id_dictionary[c['name']] = c['id']
                channel_id_to_name_dictionary[c['id']] = c['name']
            logger.info('Constructed dictionaries containing information of {} channels.'.format(str(len(request['channels']))))
            return channel_name_to_id_dictionary, channel_id_to_name_dictionary

        else:
            return None, None

    def at_operator(self, channel):
        '''
        Send a Slack message to @ the operator (the one listed on Google calendar, and temporary operator(s) if exists.)
        channel: id of the channel where the message will be sent
        '''
        if len(self.temporary_operator_id) == 0 and self.current_operator_id == "":
            self.send_message(channel, 'There is no operator on shift right now.')
        else:
            message = ""
            if self.current_operator_id != "":
                logger.debug('Found the current operator!')
                message += "<@" + self.current_operator_id + "> "
            if len(self.temporary_operator_id) != 0:
                logger.debug('Found temporary operator(s)!')
                for operator_id in self.temporary_operator_id:
                    message += "<@" + operator_id + "> "
            self.send_message(channel, message)

    def command_hello(self, channel, user_id):
        '''
        Display a greeting message in a Slack channel.
        channel: id of the channel where the message will be sent
        user_id: id of the user who called the command
        '''
        self.send_message(channel, "Hi, " + self.id_to_username_dictionary[user_id] + ".")

    def command_help(self, channel):
        '''
        Display a helper message in a Slack channel.
        channel: id of the channel where the message will be sent
        '''
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
        '''
        Display current and temporary operator(s) to a Slack channel.
        channel: id of the channel where the message will be sent
        '''
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
        '''
        Add a new temporary operator.
        channel      : id of the Slack channel where the message will be sent
        user_id      : id of the user who called the command
        operator_name: new temporary operator to be added; the user itself  will be added if empty
        '''
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
        '''
        Remove the given temporary operator.
        channel      : id of the Slack channel where the message will be sent
        user_id      : id of the user who called the command
        operator_name: the temporary operator to be removed; the user itself will be removedd if empty
        '''
        remove = user_id
        if operator_name != "":
            if operator_name not in self.username_to_id_dictionary:
                self.send_message(channel, "Sorry, I don't recognize that username.")
                return
            remove = self.username_to_id_dictionary[operator_name]
        if remove not in self.temporary_operator_id:
            self.send_message(channel, self.id_to_username_dictionary[remove] + " is not currently listed as a temporary operator.")
            return
        self.temporary_operator_id.remove(remove)
        self.send_message(channel, "Ok, you're all done. Thanks!")

    def construct_command_dictionary(self):
        '''
        Return a dictionary containing all Slack helper commands.
        '''
        self.command_dictionary["!hello"] = self.command_hello
        self.command_dictionary["!help"] = self.command_help
        self.command_dictionary["!whoisop"] = self.command_whoisop
        self.command_dictionary["!tempoperator"] = self.command_tempoperator
        self.command_dictionary["!removetempoperator"] = self.command_removetempoperator
        logger.info('Constructed dictionaries for operator helper commands on Slack.')

    def parse_output(self, rtm_output, bot_id):
        '''
        Parse the given Slack output and check whether or not I am called.
        rtm_output: Slack runtime output
        bot_id    : my bot id
        '''
        output = rtm_output
        if output and len(output) > 0:
            for o in output:
                if o and 'text' in o:
                    if ('@' + str(bot_id)) in o['text']:
                        return o['channel']
                    tokens = o['text'].split(' ', 1)
                    command = tokens[0]
                    if command in self.command_dictionary:
                        logger.info('A helper command [' + command + '] is called!')
                        channel = o["channel"]
                        user_id = o["user"]
                        operator_name = ""
                        if len(tokens) > 1 and tokens[1].startswith('[') and "]" in tokens[1]:
                            sub_tokens = tokens[1].split(']', 1)
                            operator_name = sub_tokens[0].replace('[', '')
                            logger.info('Found a potential operator name [' + operator_name + '] !')
                        func = self.command_dictionary[command]
                        num_args = len(funcsigs.signature(func).parameters)
                        args = [channel, user_id, operator_name]
                        func(*args[:num_args])
        return None
    
    def initialize(self):
        '''
        Try to check and assign values to instance variables before entering the main loop.
        Return a list of Google Calendar events if everything seems to be in order.
        '''
        logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
        self.get_slack_client()
        if self.slack_client.rtm_connect(auto_reconnect=True):
            logger.info('Connected!')
            self.bot_id = self.slack_client.api_call('auth.test')['user_id']
            if not self.bot_id:
                logger.critical('Unable to get the bot user ID.')
                os._exit(1)
            logger.info('Got Slack Operator bot id.')
            self.full_name_to_id_dictionary, self.id_to_username_dictionary, self.username_to_id_dictionary = self.construct_user_dictionaries()
            if not self.full_name_to_id_dictionary:
                logger.critical(" Cannot get the list of users.")
                os._exit(1)
            self.channel_name_to_id_dictionary, self.channel_id_to_name_dictionary = self.construct_channel_dictionaries()
            if not self.channel_name_to_id_dictionary:
                logger.error('Cannot get the list of channels, therefore cannot find the monitor channel. Related functionalities will be disabled.')
            elif self.monitor_channel_name not in self.channel_name_to_id_dictionary:
                logger.error('The name of monitor channel is not found. Related functionalities will be disabled.')
            else:
                self.monitor_channel_id = self.channel_name_to_id_dictionary[self.monitor_channel_name]
                logger.info('The id for monitor channel [' + self.monitor_channel_name + '] is found! ')

            self.construct_command_dictionary()

            self._creds = self.get_calendar_credentials()
            events = self.get_event_list(self._creds)
            if not events:
                logger.critical('Unable to find any Google Calendar event.')
                os._exit(1)
            logger.info('Successfully get ' + str(len(events)) + ' events from Google Calendar.')

            self.send_message(self.monitor_channel_id, "Have no fear, @operator is here!")

            logger.info('Trying to retrieve information regarding current operator...')
            new_operator_name, shift_end_time, self.next_shift_start_time = self.get_operator_name_and_time(events)
            self.check_operator_validity(new_operator_name, shift_end_time, True, False)
            return events
        else:
            logger.critical("An error occurs when connecting to Slack.")
            os._exit(1)

    def run(self):
        '''
        The main loop.
        '''
        events = self.initialize()
        ping_time = datetime.datetime.now() + self.ping_interval
        update_time = datetime.datetime.now() + self.update_interval
        logger.info('Next update will occur at ' + str (update_time))
        try:
            while True:
                channel = self.parse_output(self.slack_client.rtm_read(), self.bot_id)
                time_now = datetime.datetime.now()
                # ping the slack server on a regular basis to stay connected
                if time_now > ping_time
                    self.slack_client.server.ping()
                    ping_time = datetime.datetime.now() + self.ping_interval
                # Regular check and update
                if time_now > update_time:
                    # Try to update the event list
                    new_events = self.get_event_list(self._creds)
                    if not new_events:
                        logger.info('The update of Google Calendar event list fails. Information might be outdated.')
                    else:
                        events = new_events
                        logger.info('Updated the Google Calendar event list.')
                    # Try to update Slack users information
                    new_full_name_to_id_dictionary, new_id_to_username_dictionary,new_username_to_id_dictionary = self.construct_user_dictionaries()
                    if not new_full_name_to_id_dictionary:
                        logger.info("The update of Slack users information falis. Information might be outdated.")
                    else:
                        self.full_name_to_id_dictionary = new_full_name_to_id_dictionary
                        self.id_to_username_dictionary =  new_id_to_username_dictionary
                        self.username_to_id_dictionary = new_username_to_id_dictionary
                        logger.info('Updated Slack users information.')
                    # Try to update operator information -
                    new_operator_name, shift_end_time, self.next_shift_start_time = self.get_operator_name_and_time(events)
                    self.check_operator_validity(new_operator_name, shift_end_time, False, True)
                    logger.info('Updated the operator information.')
                    update_time = datetime.datetime.now() + self.update_interval
                    logger.info('Next update will occur at ' + str(update_time))
                # Update when a shift ends or it's time for next shift to start
                if time_now > self.current_shift_end_time or (self.next_shift_start_time and time_now > self.next_shift_start_time):
                    logger.info('It seems that the current operator has ended his/her shift! Trying to find a new one...')
                    new_operator_name, shift_end_time, self.next_shift_start_time = self.get_operator_name_and_time(events)
                    self.check_operator_validity(new_operator_name, shift_end_time, False, False)
                # When @operator is called
                if channel:
                    channel_name = self.channel_id_to_name_dictionary[channel]
                    logger.info('@operator is called in the channel [' + channel_name + ']! Looking for the operator...')
                    self.at_operator(channel)

                time.sleep(1)

        finally:
            logger.info('Being terminated...')
            self.send_message(self.monitor_channel_id, "I am being terminated... See you next time!")
            os._exit(0)
