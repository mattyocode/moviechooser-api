from .base import *

print("DEV SETTINGS RUN")

DEBUG = os.environ.get("DEBUG", 1)

SECRET_KEY = "insecure_key_for_dev"

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get(
            "SQL_DATABASE", os.path.join(CONFIG_BASE_DIR, "db.sqlite3")
        ),
        "USER": os.environ.get("SQL_USER", "user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
    }
}

# No SMTP locally: print emails (e.g. password-reset links) to the container log.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
