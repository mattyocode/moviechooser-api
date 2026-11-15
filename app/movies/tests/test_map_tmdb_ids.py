from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from movies.models import Movie

from .factories import MovieFactory


def run(**options):
    out = StringIO()
    call_command("map_tmdb_ids", sleep=0, stdout=out, **options)
    return out.getvalue().strip()


def tmdb_id(imdbid):
    return Movie.objects.get(imdbid=imdbid).tmdb_id


def test_match_stores_first_movie_result(fake_tmdb):
    MovieFactory(imdbid="tt0113277")
    fake_tmdb.find["tt0113277"] = 949

    assert run() == "mapped=1 unmatched=0 failed=0"
    assert tmdb_id("tt0113277") == 949


def test_no_movie_result_leaves_movie_unmapped(fake_tmdb, caplog):
    # The fake returns None for TV-only and for no results alike, as the
    # real client does (it only reads movie_results).
    MovieFactory(imdbid="tt0944947", title="Throne Tests")

    with caplog.at_level("INFO"):
        assert run() == "mapped=0 unmatched=1 failed=0"
    assert tmdb_id("tt0944947") is None
    assert "tt0944947" in caplog.text


def test_rerun_after_full_success_makes_no_requests(fake_tmdb):
    MovieFactory(imdbid="tt1")
    MovieFactory(imdbid="tt2")
    fake_tmdb.find.update({"tt1": 1, "tt2": 2})
    run()
    calls_after_first_run = len(fake_tmdb.calls)

    assert run() == "mapped=0 unmatched=0 failed=0"
    assert len(fake_tmdb.calls) == calls_after_first_run


def test_mapped_movie_is_never_looked_up_or_changed(fake_tmdb):
    MovieFactory(imdbid="tt1", tmdb_id=111)
    fake_tmdb.find["tt1"] = 999

    run()
    assert fake_tmdb.count("find") == 0
    assert tmdb_id("tt1") == 111


def test_unmatched_movie_is_retried_next_run(fake_tmdb):
    MovieFactory(imdbid="tt1")
    run()
    fake_tmdb.find["tt1"] = 7

    assert run() == "mapped=1 unmatched=0 failed=0"
    assert fake_tmdb.count("find") == 2
    assert tmdb_id("tt1") == 7


def test_one_failure_does_not_stop_the_run(fake_tmdb):
    for imdbid in ("tt1", "tt2", "tt3"):
        MovieFactory(imdbid=imdbid)
    fake_tmdb.find.update({"tt1": 1, "tt2": 2, "tt3": 3})
    fake_tmdb.fail = {"tt2"}

    assert run() == "mapped=2 unmatched=0 failed=1"
    assert [tmdb_id(i) for i in ("tt1", "tt2", "tt3")] == [1, None, 3]


def test_missing_token_is_an_error_and_changes_nothing(db, settings):
    settings.TMDB_READ_TOKEN = None
    MovieFactory(imdbid="tt1")

    with pytest.raises(CommandError, match="TMDB_READ_TOKEN"):
        run()
    assert tmdb_id("tt1") is None


def test_limit_caps_lookups(fake_tmdb):
    for imdbid in ("tt1", "tt2", "tt3"):
        MovieFactory(imdbid=imdbid)
    fake_tmdb.find.update({"tt1": 1, "tt2": 2, "tt3": 3})

    assert run(limit=2) == "mapped=2 unmatched=0 failed=0"
    assert fake_tmdb.count("find") == 2
    assert tmdb_id("tt3") is None


def test_daily_task_runs_the_command(fake_tmdb):
    from movies.tasks import map_tmdb_ids

    MovieFactory(imdbid="tt1")
    fake_tmdb.find["tt1"] = 1
    map_tmdb_ids()
    assert tmdb_id("tt1") == 1
