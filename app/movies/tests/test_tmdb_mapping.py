import pytest

from movies import tmdb
from movies.models import Movie
from movies.tmdb_mapping import MappingResult, map_tmdb_ids

from .factories import MovieFactory


def run(**options):
    return map_tmdb_ids(sleep=0, **options)


def tmdb_id(imdbid):
    return Movie.objects.get(imdbid=imdbid).tmdb_id


def test_match_stores_first_movie_result(fake_tmdb):
    MovieFactory(imdbid="tt0113277")
    fake_tmdb.find["tt0113277"] = 949

    assert run() == MappingResult(mapped=1, unmatched=0, failed=0)
    assert tmdb_id("tt0113277") == 949


def test_match_stores_poster_path_from_the_same_lookup(fake_tmdb):
    MovieFactory(imdbid="tt0113277")
    fake_tmdb.find["tt0113277"] = tmdb.TMDBMatch(id=949, poster_path="/heat.jpg")

    run()

    movie = Movie.objects.get(imdbid="tt0113277")
    assert (movie.tmdb_id, movie.poster_path) == (949, "/heat.jpg")
    assert fake_tmdb.calls == [("find", "tt0113277")]


def test_match_without_poster_leaves_path_empty(fake_tmdb):
    MovieFactory(imdbid="tt0113277")
    fake_tmdb.find["tt0113277"] = tmdb.TMDBMatch(id=949, poster_path=None)

    run()

    movie = Movie.objects.get(imdbid="tt0113277")
    assert (movie.tmdb_id, movie.poster_path) == (949, None)


def test_no_movie_result_leaves_movie_unmapped(fake_tmdb, caplog):
    # The fake returns None for TV-only and for no results alike, as the
    # real client does (it only reads movie_results).
    MovieFactory(imdbid="tt0944947", title="Throne Tests")

    with caplog.at_level("INFO"):
        assert run() == MappingResult(mapped=0, unmatched=1, failed=0)
    assert tmdb_id("tt0944947") is None
    assert "tt0944947" in caplog.text


def test_rerun_after_full_success_makes_no_requests(fake_tmdb):
    MovieFactory(imdbid="tt1")
    MovieFactory(imdbid="tt2")
    fake_tmdb.find.update({"tt1": 1, "tt2": 2})
    run()
    calls_after_first_run = len(fake_tmdb.calls)

    assert run() == MappingResult(mapped=0, unmatched=0, failed=0)
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

    assert run() == MappingResult(mapped=1, unmatched=0, failed=0)
    assert fake_tmdb.count("find") == 2
    assert tmdb_id("tt1") == 7


def test_one_failure_does_not_stop_the_run(fake_tmdb):
    for imdbid in ("tt1", "tt2", "tt3"):
        MovieFactory(imdbid=imdbid)
    fake_tmdb.find.update({"tt1": 1, "tt2": 2, "tt3": 3})
    fake_tmdb.fail = {"tt2"}

    assert run() == MappingResult(mapped=2, unmatched=0, failed=1)
    assert [tmdb_id(i) for i in ("tt1", "tt2", "tt3")] == [1, None, 3]


def test_missing_token_raises_and_changes_nothing(db, settings):
    settings.TMDB_READ_TOKEN = None
    MovieFactory(imdbid="tt1")

    with pytest.raises(tmdb.TMDBNotConfigured):
        run()
    assert tmdb_id("tt1") is None


def test_limit_caps_lookups(fake_tmdb):
    for imdbid in ("tt1", "tt2", "tt3"):
        MovieFactory(imdbid=imdbid)
    fake_tmdb.find.update({"tt1": 1, "tt2": 2, "tt3": 3})

    assert run(limit=2) == MappingResult(mapped=2, unmatched=0, failed=0)
    assert fake_tmdb.count("find") == 2
    assert tmdb_id("tt3") is None


def test_result_reads_as_the_summary_line():
    assert str(MappingResult(mapped=2, unmatched=0, failed=1)) == (
        "mapped=2 unmatched=0 failed=1"
    )


def test_daily_task_maps_movies_and_returns_the_counts(fake_tmdb):
    from movies.tasks import map_tmdb_ids as task

    MovieFactory(imdbid="tt1")
    fake_tmdb.find["tt1"] = 1

    assert task() == {"mapped": 1, "unmatched": 0, "failed": 0}
    assert tmdb_id("tt1") == 1


def test_daily_task_does_not_go_through_the_management_command(fake_tmdb, monkeypatch):
    from movies.management.commands.map_tmdb_ids import Command
    from movies.tasks import map_tmdb_ids as task

    def no_commands(*args, **kwargs):
        raise AssertionError("the task should call the mapping function directly")

    # Patching the command itself catches call_command however it's imported.
    monkeypatch.setattr(Command, "handle", no_commands)
    task()
