from .base import *

print("LOCAL SETTINGS RUN")

DEBUG = 1

SECRET_KEY = os.environ.get("SECRET_KEY")

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE"),
        "NAME": os.environ.get("LOCAL_SQL_DATABASE"),
        "USER": os.environ.get("LOCAL_SQL_USER"),
        "PASSWORD": os.environ.get("LOCAL_SQL_PASSWORD"),
        "HOST": os.environ.get("LOCAL_SQL_HOST"),
        "PORT": os.environ.get("LOCAL_SQL_PORT"),
    }
}
