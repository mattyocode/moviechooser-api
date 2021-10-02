from .base import *


DEBUG = 0

if not DEBUG:
    REST_FRAMEWORK = {
        "DEFAULT_RENDERER_CLASSES": (
            "rest_framework.renderers.JSONRenderer",
        )
    }

SECRET_KEY = os.environ.get("SECRET_KEY")

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE"),
        "NAME": os.environ.get("PROD_SQL_DATABASE"),
        "USER": os.environ.get("PROD_SQL_USER"),
        "PASSWORD": os.environ.get("PROD_SQL_PASSWORD"),
        "HOST": os.environ.get("PROD_SQL_HOST"),
        "PORT": os.environ.get("PROD_SQL_PORT"),
    }
}