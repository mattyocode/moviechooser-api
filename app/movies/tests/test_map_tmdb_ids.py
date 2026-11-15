"""The map_tmdb_ids command's own job: options, output and errors.

The mapping behaviour itself is tested in test_tmdb_mapping.py.
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from movies.models import Movie

from .factories import MovieFactory


def run(*args, **options):
    out = StringIO()
    call_command("map_tmdb_ids", *args, stdout=out, **options)
    return out.getvalue().strip()


def test_prints_the_summary_line(fake_tmdb):
    for imdbid in ("tt1", "tt2", "tt3"):
        MovieFactory(imdbid=imdbid)
    fake_tmdb.find.update({"tt1": 1, "tt3": 3})
    fake_tmdb.fail = {"tt3"}

    assert run(sleep=0) == "mapped=1 unmatched=1 failed=1"


def test_missing_token_is_a_command_error_naming_the_setting(db, settings):
    settings.TMDB_READ_TOKEN = None
    MovieFactory(imdbid="tt1")

    with pytest.raises(CommandError, match="TMDB_READ_TOKEN"):
        run()
    assert Movie.objects.get(imdbid="tt1").tmdb_id is None


def test_limit_option_is_passed_through(fake_tmdb):
    for imdbid in ("tt1", "tt2", "tt3"):
        MovieFactory(imdbid=imdbid)
    fake_tmdb.find.update({"tt1": 1, "tt2": 2, "tt3": 3})

    assert run("--limit", "2", "--sleep", "0") == "mapped=2 unmatched=0 failed=0"
    assert fake_tmdb.count("find") == 2


def test_negative_sleep_is_rejected(db):
    with pytest.raises(CommandError):
        run("--sleep", "-1")
