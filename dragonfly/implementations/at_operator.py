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
        self.bot_id = None

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

    # get a list of events beging 
    def get_event_list(self, creds, length):
        service = build('calendar', 'v3', http=creds.authorize(Http()))
        time = datetime.datetime.now().isoformat() + 'Z'
        events_list = service.events().list(calendarId='primary', timeMin=time, 
                                            maxResults=length, singleEvents=True, 
                                            orderBy='startTime').execute()
        events = events_list.get('items', [])
        if not events:
            raise Exception('No events found.')
        result = []
        for event in events:
            result.append(event['summary'])
        return result

    def get_operator_name(self, event_list):
        return 'a random dude'

    def get_operator_id(self, name):
        return 'UDsomething'

    def at_operator(self, channel, operator_id):
        self.slack_client.api_call("chat.postMessage", channel=channel, text='got it!', 
                                    as_user=True)
        self.slack_client.api_call("chat.postMessage", link_names=1, channel=channel, 
                                    text='<@' + operator_id + '>', as_user=True)


    def parse_output(self, rtm_output):
        output = rtm_output
        if output and len(output) > 0:
            for o in output:
                if o and 'text' in o and ('@' + str(self.bot_id)) in o['text']:
                    return o['channel']
        return None, None



    def run(self):
        logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
        if self.slack_client.rtm_connect():
            logging.info('connected!')
            self.bot_id = self.slack_client.api_call('auth.test')['user_id']
            while True:
                channel = self.parse_output(self.slack_client.rtm_read())
                if channel:
                    creds = self.get_credentials()
                    event_list = self.get_event_list(creds, 50)
                    operator_name = self.get_operator_name(event_list)
                    operator_id = self.get_operator_id(operator_name)
                    self.at_operator(channel, operator_id)
                time.sleep(1)
        else:
            logging.error("fail!!!")



if __name__ == '__main__':
    o = AtOperator()
    o.run()
