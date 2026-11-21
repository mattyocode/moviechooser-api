"""The check_posters command's own job: output, the 5% rule and errors.

The check itself is tested in test_posters.py.
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from movies.models import Movie
from movies.posters import PosterCheckFailed

from .factories import MovieFactory


def run(out):
    call_command("check_posters", sleep=0, stdout=out)


def test_one_broken_one_fixed_one_missing(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/healthy.jpg")
    MovieFactory(imdbid="tt2", tmdb_id=2, poster_path="/old.jpg")
    MovieFactory(imdbid="tt3", tmdb_id=3, poster_path="/stuck.jpg")
    MovieFactory(imdbid="tt4", tmdb_id=4, poster_path=None)
    images.statuses.update({"/old.jpg": [404], "/stuck.jpg": [404]})
    fake_tmdb.posters.update({2: "/new.jpg", 4: None})
    fake_tmdb.fail = {3}
    out = StringIO()

    with pytest.raises(CommandError, match="5%"):
        run(out)

    assert out.getvalue().strip() == "checked=3 fixed=1 missing=1 broken=1"
    paths = dict(Movie.objects.values_list("imdbid", "poster_path"))
    assert paths == {
        "tt1": "/healthy.jpg",
        "tt2": "/new.jpg",
        "tt3": "/stuck.jpg",
        "tt4": None,
    }


def test_clean_run_succeeds(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/healthy.jpg")
    out = StringIO()

    run(out)

    assert out.getvalue().strip() == "checked=1 fixed=0 missing=0 broken=0"


def test_missing_token_is_a_command_error_naming_the_setting(db, settings, images):
    settings.TMDB_READ_TOKEN = None
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/old.jpg")
    images.statuses["/old.jpg"] = [404]

    with pytest.raises(CommandError, match="TMDB_READ_TOKEN"):
        run(StringIO())
    assert Movie.objects.get(imdbid="tt1").poster_path == "/old.jpg"
    assert images.requests == []


def test_weekly_task_returns_the_counts(fake_tmdb, images):
    from movies.tasks import check_posters as task

    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path=None)
    fake_tmdb.posters[1] = "/found.jpg"

    assert task() == {"checked": 0, "fixed": 1, "missing": 0, "broken": 0}
    assert Movie.objects.get(imdbid="tt1").poster_path == "/found.jpg"


def test_weekly_task_fails_over_the_threshold(fake_tmdb, images, caplog):
    from movies.tasks import check_posters as task

    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/stuck.jpg")
    images.statuses["/stuck.jpg"] = [404]
    fake_tmdb.fail = {1}

    with pytest.raises(PosterCheckFailed, match="broken=1"):
        task()
    assert "checked=1 fixed=0 missing=0 broken=1" in caplog.text


def test_weekly_schedule_entry(settings):
    entry = settings.CELERY_BEAT_SCHEDULE["check-posters"]
    assert entry["task"] == "movies.tasks.check_posters"
    schedule = entry["schedule"]
    assert (schedule.day_of_week, schedule.hour, schedule.minute) == (
        {0},
        {3},
        {0},
    )
