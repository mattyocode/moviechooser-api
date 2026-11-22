"""check_posters: verify stored poster paths, then repair broken and missing ones.

TMDB API calls go to fake_tmdb. Image requests go to the images fixture
(FakeImages in conftest.py), which sits below the real head() so its
retries are exercised too.
"""

from datetime import timedelta

import pytest
import requests
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.utils import timezone

from movies import posters, tmdb
from movies.models import Movie
from movies.posters import PosterCheckResult, check_posters
from movies.utils import recommendable_movies

from .factories import MovieFactory


def run(fake_tmdb):
    return check_posters(sleep=0)


def path(imdbid):
    return Movie.objects.get(imdbid=imdbid).poster_path


def test_all_images_load_makes_no_tmdb_calls(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/a.jpg")
    MovieFactory(imdbid="tt2", tmdb_id=2, poster_path="/b.jpg")

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=2, fixed=0, missing=0, broken=0)
    assert fake_tmdb.calls == []
    assert [path("tt1"), path("tt2")] == ["/a.jpg", "/b.jpg"]
    assert sorted(images.requests) == [
        "https://image.tmdb.org/t/p/w342/a.jpg",
        "https://image.tmdb.org/t/p/w342/b.jpg",
    ]


def test_transient_failure_is_retried_and_not_reread(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/a.jpg")
    images.statuses["/a.jpg"] = [503, 200]

    result = run(fake_tmdb)

    assert result.broken == 0
    assert images.count("/a.jpg") == 2
    assert fake_tmdb.count("poster") == 0


def test_broken_path_is_replaced_and_checked(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/old.jpg")
    images.statuses["/old.jpg"] = [404]
    fake_tmdb.posters[1] = "/new.jpg"

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=1, fixed=1, missing=0, broken=0)
    assert path("tt1") == "/new.jpg"
    assert images.count("/old.jpg") == 1  # a 404 is final, not retried
    assert images.count("/new.jpg") == 1


def test_missing_path_is_backfilled(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path=None)
    fake_tmdb.posters[1] = "/found.jpg"

    result = run(fake_tmdb)

    # The new path's image was checked, so it counts as checked.
    assert result == PosterCheckResult(checked=1, fixed=1, missing=0, broken=0)
    assert path("tt1") == "/found.jpg"
    assert images.count("/found.jpg") == 1


def test_first_run_with_every_new_poster_broken_is_over_the_threshold(
    fake_tmdb, images
):
    # The backfill: nothing had a path, so phase 1 checks nothing, but every
    # path TMDB gives fails to load.
    for n in range(20):
        MovieFactory(imdbid=f"tt{n}", tmdb_id=n, poster_path=None)
        fake_tmdb.posters[n] = f"/p{n}.jpg"
        images.statuses[f"/p{n}.jpg"] = [404]

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=20, fixed=0, missing=0, broken=20)
    assert result.problem() is not None


def test_an_empty_path_is_rejected(db):
    with pytest.raises(IntegrityError), transaction.atomic():
        MovieFactory(imdbid="tt1", poster_path="")


def test_tmdb_has_no_poster(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/gone.jpg", review=[80])
    images.statuses["/gone.jpg"] = [404]
    fake_tmdb.posters[1] = None

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=1, fixed=0, missing=1, broken=0)
    assert path("tt1") is None
    assert recommendable_movies(AnonymousUser()).filter(imdbid="tt1").exists()


def test_unmapped_movie_makes_no_request_and_counts_missing(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=None, poster_path=None)

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=0, fixed=0, missing=1, broken=0)
    assert fake_tmdb.calls == []
    assert images.requests == []


def test_tmdb_lookup_failure_leaves_path_and_counts_broken(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/old.jpg")
    MovieFactory(imdbid="tt2", tmdb_id=2, poster_path="/old2.jpg")
    images.statuses["/old.jpg"] = [404]
    images.statuses["/old2.jpg"] = [404]
    fake_tmdb.fail = {1}
    fake_tmdb.posters[2] = "/new2.jpg"

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=2, fixed=1, missing=0, broken=1)
    assert path("tt1") == "/old.jpg"
    assert path("tt2") == "/new2.jpg"


def test_tmdb_giving_the_same_broken_path_counts_broken(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/same.jpg")
    images.statuses["/same.jpg"] = [404]
    fake_tmdb.posters[1] = "/same.jpg"

    result = run(fake_tmdb)

    assert result.broken == 1
    assert images.count("/same.jpg") == 2  # checked again before counting it


def test_same_path_that_loads_on_a_second_check_is_not_broken(fake_tmdb, images):
    # A passing outage during phase 1.
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/same.jpg")
    images.statuses["/same.jpg"] = [404, 200]
    fake_tmdb.posters[1] = "/same.jpg"

    result = run(fake_tmdb)

    assert result == PosterCheckResult(checked=1, fixed=0, missing=0, broken=0)
    assert path("tt1") == "/same.jpg"


def test_new_path_that_does_not_load_counts_broken(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/old.jpg")
    images.statuses["/old.jpg"] = [404]
    images.statuses["/new.jpg"] = [404]
    fake_tmdb.posters[1] = "/new.jpg"

    result = run(fake_tmdb)

    assert (result.fixed, result.broken) == (0, 1)
    assert path("tt1") == "/new.jpg"


@pytest.mark.parametrize("broken, failed", [(5, False), (6, True)])
def test_five_percent_threshold(broken, failed):
    result = PosterCheckResult(checked=100, fixed=0, missing=0, broken=broken)
    assert (result.problem() is not None) is failed


def test_threshold_message_comes_from_the_setting(monkeypatch):
    monkeypatch.setattr(posters, "MAX_BROKEN_SHARE", 0.1)
    result = PosterCheckResult(checked=100, fixed=0, missing=0, broken=11)
    assert result.problem().startswith("More than 10% of posters still broken")


def test_nothing_checked_has_no_problem():
    result = PosterCheckResult(checked=0, fixed=0, missing=3, broken=0)
    assert result.problem() is None


def test_summary_line():
    result = PosterCheckResult(checked=3, fixed=1, missing=1, broken=1)
    assert str(result) == "checked=3 fixed=1 missing=1 broken=1"
    incomplete = PosterCheckResult(1, 0, 0, 0, complete=False)
    assert str(incomplete) == "checked=1 fixed=0 missing=0 broken=0 incomplete"


def test_out_of_time_stops_new_work_and_is_a_problem(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/a.jpg")
    MovieFactory(imdbid="tt2", tmdb_id=2, poster_path=None)

    result = check_posters(sleep=0, time_budget=0)

    assert result.complete is False
    assert (result.checked, result.broken) == (0, 0)
    assert images.requests == []
    assert fake_tmdb.count("poster") == 0
    assert result.problem().startswith("Ran out of time")


def test_lookups_run_in_parallel_workers(fake_tmdb, images, monkeypatch):
    import threading

    seen = set()
    real = fake_tmdb.movie_poster_path

    def recording(tmdb_id):
        seen.add(threading.get_ident())
        return real(tmdb_id)

    monkeypatch.setattr(fake_tmdb, "movie_poster_path", recording)
    for n in range(8):
        MovieFactory(imdbid=f"tt{n}", tmdb_id=n, poster_path=None)
        fake_tmdb.posters[n] = f"/p{n}.jpg"

    assert run(fake_tmdb).fixed == 8
    assert threading.get_ident() not in seen  # none on the main thread


def test_store_leaves_a_movie_changed_during_the_run(db):
    MovieFactory(imdbid="tt1", tmdb_id=2, poster_path="/fixed-by-hand.jpg")

    # The run read tmdb_id=1 and /old.jpg before an admin changed them.
    assert posters._store("tt1", 1, "/old.jpg", poster_path="/wrong.jpg") is False
    assert path("tt1") == "/fixed-by-hand.jpg"
    assert posters._store("tt1", 2, "/fixed-by-hand.jpg", poster_path="/n.jpg")
    assert path("tt1") == "/n.jpg"


def test_no_poster_answer_is_remembered(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path=None)
    fake_tmdb.posters[1] = None

    run(fake_tmdb)
    stamped = Movie.objects.get(imdbid="tt1").no_poster_checked_at
    run(fake_tmdb)

    assert stamped is not None
    assert fake_tmdb.count("poster") == 1  # not asked again a week later


def test_no_poster_answer_is_rechecked_after_the_interval(fake_tmdb, images):
    long_ago = timezone.now() - posters.NO_POSTER_RECHECK - timedelta(days=1)
    MovieFactory(
        imdbid="tt1", tmdb_id=1, poster_path=None, no_poster_checked_at=long_ago
    )
    fake_tmdb.posters[1] = "/arrived.jpg"

    assert run(fake_tmdb).fixed == 1
    movie = Movie.objects.get(imdbid="tt1")
    assert (movie.poster_path, movie.no_poster_checked_at) == ("/arrived.jpg", None)


def test_sessions_are_closed(fake_tmdb, images):
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/a.jpg")

    run(fake_tmdb)

    assert images.closed >= 1


def test_head_without_a_session_closes_its_own(images):
    assert posters.head(posters.image_url("/a.jpg")) is True
    assert images.closed == 1


def test_missing_token_raises_before_any_request(db, settings, images):
    settings.TMDB_READ_TOKEN = None
    MovieFactory(imdbid="tt1", tmdb_id=1, poster_path="/a.jpg")

    with pytest.raises(tmdb.TMDBNotConfigured):
        check_posters(sleep=0)

    assert images.requests == []


# The default head(), against a patched requests.Session.head.


@pytest.fixture
def session_head(monkeypatch):
    calls = []
    outcomes = []
    sleeps = []

    def fake_head(self, url, **kwargs):
        calls.append((url, kwargs))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        response = requests.Response()
        response.status_code = outcome
        return response

    monkeypatch.setattr(requests.Session, "head", fake_head)
    monkeypatch.setattr(posters.time, "sleep", sleeps.append)
    return calls, outcomes, sleeps


def test_head_follows_redirects_with_timeout(session_head):
    calls, outcomes, _ = session_head
    outcomes.append(200)

    assert posters.head("https://image.tmdb.org/t/p/w342/a.jpg") is True
    assert calls == [
        (
            "https://image.tmdb.org/t/p/w342/a.jpg",
            {"allow_redirects": True, "timeout": 5},
        )
    ]


def test_head_does_not_retry_a_404(session_head):
    calls, outcomes, sleeps = session_head
    outcomes.append(404)

    assert posters.head("u") is False
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "failure", [requests.Timeout("slow"), 503, 429, requests.ConnectionError("x")]
)
def test_head_retries_up_to_three_attempts(session_head, failure):
    calls, outcomes, sleeps = session_head
    outcomes.extend([failure, failure, failure])

    assert posters.head("u") is False
    assert len(calls) == 3
    assert sleeps == [0.5, 1]


def test_head_succeeds_on_a_retry(session_head):
    calls, outcomes, sleeps = session_head
    outcomes.extend([requests.Timeout("slow"), 200])

    assert posters.head("u") is True
    assert len(calls) == 2
    assert sleeps == [0.5]
