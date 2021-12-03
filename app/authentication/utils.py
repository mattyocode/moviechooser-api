import os
import threading
import time

import requests
from django.core.mail import EmailMessage

recaptcha_secret_key = os.environ.get("RECAPTCHA_SECRET_KEY")
# ENV = os.environ.get("ENV_NAME")


def recaptcha_submit(token):
    response = requests.post(
        f"https://www.google.com/recaptcha/api/siteverify?secret={recaptcha_secret_key}&response={token}",
    )
    response = response.json()
    # if ENV == "local":
    #     response["success"] = True
    return response["success"]


class EmailThread(threading.Thread):
    def __init__(self, subject, message, sender, recipient_list):
        self.subject = subject
        self.message = message
        self.sender = sender
        self.recipient_list = recipient_list
        self._stopevent = threading.Event()
        threading.Thread.__init__(self)

    def stopped(self):
        return self._stopevent.isSet()

    def run(self):
        email = EmailMessage(
            self.subject, self.message, self.sender, self.recipient_list
        )
        email.send(fail_silently=False)

    def join(self, timeout=None):
        """Stop the thread."""
        self._stopevent.set()
        threading.Thread.join(self, timeout)


def send_email(subject, message, sender, recipient_list):
    emailthread = EmailThread(subject, message, sender, recipient_list)
    emailthread.start()
    time.sleep(5.0)
    emailthread.join()
