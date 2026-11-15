"""Every beat schedule entry must name a task the Celery app has registered.

Beat only finds out a task name is wrong when it fires, and then it just
logs an error. This catches the typo in CI instead.
"""

from django.conf import settings

from config.celery import app


def unknown_schedule_tasks(schedule):
    app.loader.import_default_modules()
    return sorted(
        f"{name} -> {entry['task']}"
        for name, entry in schedule.items()
        if entry["task"] not in app.tasks
    )


def test_beat_schedule_names_registered_tasks():
    assert unknown_schedule_tasks(settings.CELERY_BEAT_SCHEDULE) == []


def test_unknown_task_is_reported(settings):
    settings.CELERY_BEAT_SCHEDULE = {
        "bad": {"task": "movies.tasks.nope", "schedule": 60},
    }
    assert unknown_schedule_tasks(settings.CELERY_BEAT_SCHEDULE) == [
        "bad -> movies.tasks.nope"
    ]
