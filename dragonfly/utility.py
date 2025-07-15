import elog
from getpass import getpass


def send_to_elog(message, subject="Checklist", author="Rene Reimann", category="Slow Controls"):
    password = getpass()
    logbook = elog.open("https://maxwell.npl.washington.edu/elog/project8/P8+Mainz+lab", user="rreimann", password=password)
    return logbook.post(message, subject=subject, Author=author, category=category, suppress_email_notification=True)
