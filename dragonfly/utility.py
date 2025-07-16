import elog
from getpass import getpass


def send_to_elog(message, subject="Checklist", author="Rene Reimann", category="Slow Controls", msg_id=None):
    password = getpass()
    logbook = elog.open("https://maxwell.npl.washington.edu/elog/project8/P8+Mainz+lab", user="rreimann", password=password)
    if msg_id is None:
       return logbook.post(message, subject=subject, Author=author, category=category, suppress_email_notification=True)
    else:
       return logbook.post(message, msg_id=msg_id, subject=subject, Author=author, category=category, suppress_email_notification=True)
