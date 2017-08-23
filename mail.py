from database import *
from jinja2 import Template
from datetime import datetime, timedelta
from pony import orm
from itertools import groupby
import requests
import smtplib
from email.mime.text import MIMEText
import os

SMTP_LOGIN = os.environ['VIJOURNALBOT_SMTP_LOGIN']
SMTP_PASSWORD = os.environ['VIJOURNALBOT_SMTP_PASSWORD']
SMTP_SERVER = os.environ['VIJOURNALBOT_SMTP_SERVER']

with open('mailtemplate.jinja2') as f:
    mailtemplate_file = f.read()

mailtemplate = Template(mailtemplate_file)

def prepare_mail(user):
    time_now = datetime.now()
    week_ago = time_now - timedelta(days=7)
    week_updates = (user.updates
                .filter(lambda u: u.timestamp > week_ago)
                .order_by(Update.timestamp))

    updates_by_day = groupby(week_updates, lambda u: u.timestamp.date())

    mail = mailtemplate.render(
        user=user,
        updates_by_day=updates_by_day,
        start=week_ago,
        end=time_now)
    
    return mail

def send_mail(address, subject, text):
    msg = MIMEText(text)
    msg['Subject'] = subject
    msg['From']    = SMTP_LOGIN
    msg['To']      = address
    s = smtplib.SMTP(SMTP_SERVER, 587)
    s.login(SMTP_LOGIN, SMTP_PASSWORD)
    s.sendmail(msg['From'], msg['To'], msg.as_string())
    s.quit()

def send_out_weekly_recap():
    for user in orm.select(u for u in User):
        mail = prepare_mail(user)
        print "sending mail to " + user.email
        if user.email:
            print send_mail(user.email, "Your weekly journal entries", mail)

@orm.db_session
def main():
    db.bind(provider='sqlite', filename='./data/database.sqlite')
    db.generate_mapping()
    send_out_weekly_recap()

if __name__ == '__main__':
    main()