from .base import *

print("PROD SETTINGS RUN")

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 30,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

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

CORS_ALLOWED_ORIGINS = ["https://*"]
CORS_ORIGIN_ALLOW_ALL = True
CORS_ORIGIN_WHITELIST = ["*"]
# CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS").split(" ")
