import datetime, logging, os, time
# for google
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
# for slack
from slackclient import SlackClient
logging.basicConfig()

# need to export BOT_TOKEN first
class AtOperator():
    
    def __init__(self):

        self.calendar_scope = 'https://www.googleapis.com/auth/calendar.readonly'
        self.slack_client = SlackClient(os.environ.get('BOT_TOKEN'))

        self.current_operator_name = None
        self.current_operator_id = None
        self.expire_time = datetime.datetime(2000, 1, 1, 0, 0, 0, 0).isoformat() + 'Z'


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

    def get_event_list(self, creds, length):
        service = build('calendar', 'v3', http=creds.authorize(Http()))
        time_now = datetime.datetime.now().isoformat() + 'Z'
        events_list = service.events().list(calendarId='primary', timeMin=time_now, 
                                            maxResults=length, singleEvents=True, 
                                            orderBy='startTime').execute()
        events = events_list.get('items', [])
        if not events:
            raise Exception('No events found.')
        return events

    def get_operator_name_and_expiration_time(self, events):
        for event in events:
            if 'Operator:' in event['summary']:
                name = event['summary'].replace('Operator: ', '')
                if event['end']['datetime'] != '':
                    return name, event['end']['datetime']
                else:
                    return name, datetime.datetime.combine(event['end']['date'], datetime.datetime.max.time())
        #name = 'Yadi'
        #expiration_time = datetime.datetime.today()
        #return name, expiration_time
        return None, None

    def construct_id_dictionary(self):
        request = self.slack_client.api_call("users.list")
        if request['ok']:
            id_dictionary = {}
            for m in request['members']:
                if not m['is_bot']:
                    id_dictionary[m['real_name']] = m['id']
            return id_dictionary
        else:
            raise Exception('Cannot get the list of users')

    def at_operator(self, channel, operator_id):
        self.slack_client.api_call("chat.postMessage", channel=channel, text='Get it!', 
                                   as_user=True)
        self.slack_client.api_call("chat.postMessage", link_names=1, channel=channel, 
                                   text='<@' + operator_id + '>', as_user=True)


    def parse_output(self, rtm_output, bot_id):
        output = rtm_output
        if output and len(output) > 0:
            for o in output:
                if o and 'text' in o and ('@' + str(bot_id)) in o['text']:
                    return o['channel']
        return None, None



    def run(self):
        logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
        if self.slack_client.rtm_connect():
            logging.info('connected!')
            bot_id = self.slack_client.api_call('auth.test')['user_id']
            id_dictionary = self.construct_id_dictionary()
            while True:
                channel = self.parse_output(self.slack_client.rtm_read(), bot_id)
                if channel:
                    # if saved information for current operator is out-of-date,
                    # update it by going to the Google calendar
                    time_now = datetime.datetime.now().isoformat() + 'Z'
                    if str(time_now) > str(self.expiration_time):
                        creds = self.get_credentials()
                        events = self.get_event_list(creds, 50)
                        new_operator_name, new_expiration_time = self.get_operator_name_and_expiration_time(events)
                        if not new_operator_name:
                            self.slack_client.api_call("chat.postMessage", 
                                                       channel=channel, 
                                                       text='No operator is on duty now.', 
                                                       as_user=True)
                        else:
                            if new_operator_name in id_dictionary:
                                self.expiration_time = new_expiration_time
                                if new_operator_name != self.current_operator_name:
                                    self.current_operator_name = new_operator_name
                                    self.current_operator_id =id_dictionary[self.current_operator_name]
                               
                            else:
                                raise Exception('The operator listed on Google calendar is not found in Slack.')
                     self.at_operator(channel, self.current_operator_id)
                time.sleep(1)
        else:
            logging.error("fail!!!")



if __name__ == '__main__':
    o = AtOperator()
    o.run()
