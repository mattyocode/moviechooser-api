import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings.base")

app = Celery("app", includes=["movies.tasks"])
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {"movies.tasks.fetch_movies": {"queue": "mc_task_queue"}}
