import os
import threading

import requests
from django.core.mail import EmailMessage

recaptcha_secret_key = os.environ.get("RECAPTCHA_SECRET_KEY")


def recaptcha_submit(token):
    response = requests.post(
        f"https://www.google.com/recaptcha/api/siteverify?secret={recaptcha_secret_key}&response={token}",
    )
    response = response.json()
    return response["success"]


class EmailThread(threading.Thread):
    def __init__(self, subject, message, sender, recipient_list):
        self.subject = subject
        self.message = message
        self.sender = sender
        self.recipient_list = recipient_list
        threading.Thread.__init__(self)

    def run(self):
        email = EmailMessage(
            self.subject, self.message, self.sender, self.recipient_list
        )
        email.send()


def send_email(subject, message, sender, recipient_list):
    EmailThread(subject, message, sender, recipient_list).start()
