import os

import requests

recaptcha_secret_key = os.environ.get("RECAPTCHA_SECRET_KEY")

def recaptcha_submit(token):
    response = requests.post(
        f"https://www.google.com/recaptcha/api/siteverify?secret={recaptcha_secret_key}&response={token}",
    )
    response = response.json()
    return response["success"]
