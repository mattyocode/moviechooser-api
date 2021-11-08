from .base import *

print("PROD SETTINGS RUN")

SECRET_KEY = os.environ.get("SECRET_KEY")

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("SQL_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("SQL_DATABASE", os.path.join(BASE_DIR, "db.sqlite3")),
        "USER": os.environ.get("SQL_USER", "user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "password"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
    }
}

CORS_ALLOWED_ORIGINS = ["https://moviechooser.co.uk"]
CORS_ORIGIN_ALLOW_ALL = True
CORS_ORIGIN_WHITELIST = ["https://moviechooser.co.uk"]
# Add comment
