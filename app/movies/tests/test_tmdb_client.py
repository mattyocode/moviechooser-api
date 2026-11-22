from unittest import mock

import pytest
import requests

from movies.tmdb import (
    TIMEOUT,
    TMDBClient,
    TMDBError,
    TMDBMatch,
    TMDBNotConfigured,
    get_tmdb_client,
)


def fake_response(json_data=None, status=200, json_error=False):
    response = mock.Mock()
    response.status_code = status
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"{status} Error", response=response
        )
    else:
        response.raise_for_status.return_value = None
    if json_error:
        response.json.side_effect = ValueError("bad json")
    else:
        response.json.return_value = json_data
    return response


@pytest.fixture
def session():
    s = requests.Session()
    s.get = mock.Mock()
    return s


def test_token_sent_as_bearer_header_not_in_url(session):
    session.get.return_value = fake_response({"movie_results": []})
    TMDBClient("secret-token", session=session).find_movie("tt0113277")

    assert session.headers["Authorization"] == "Bearer secret-token"
    args, kwargs = session.get.call_args
    assert "secret-token" not in args[0]
    assert "secret-token" not in str(kwargs.get("params"))


def test_find_uses_imdb_external_source_and_timeout(session):
    session.get.return_value = fake_response({"movie_results": []})
    TMDBClient("t", session=session).find_movie("tt0113277")

    args, kwargs = session.get.call_args
    assert args[0] == "https://api.themoviedb.org/3/find/tt0113277"
    assert kwargs["params"] == {"external_source": "imdb_id"}
    assert kwargs["timeout"] == TIMEOUT == 3


def test_find_returns_first_movie_result_with_poster_path(session):
    session.get.return_value = fake_response(
        {
            "movie_results": [
                {"id": 949, "poster_path": "/heat.jpg"},
                {"id": 1, "poster_path": "/other.jpg"},
            ],
            "tv_results": [],
        }
    )
    assert TMDBClient("t", session=session).find_movie("tt0113277") == TMDBMatch(
        id=949, poster_path="/heat.jpg"
    )


@pytest.mark.parametrize("result", [{"id": 949, "poster_path": None}, {"id": 949}])
def test_find_without_poster_gives_none_path(session, result):
    session.get.return_value = fake_response({"movie_results": [result]})
    match = TMDBClient("t", session=session).find_movie("tt0113277")
    assert match == TMDBMatch(id=949, poster_path=None)


def test_find_ignores_tv_results(session):
    session.get.return_value = fake_response(
        {"movie_results": [], "tv_results": [{"id": 1399}]}
    )
    assert TMDBClient("t", session=session).find_movie("tt0944947") is None


def test_movie_poster_path_reads_movie_details(session):
    session.get.return_value = fake_response({"id": 949, "poster_path": "/new.jpg"})
    assert TMDBClient("t", session=session).movie_poster_path(949) == "/new.jpg"

    args, kwargs = session.get.call_args
    assert args[0] == "https://api.themoviedb.org/3/movie/949"
    assert kwargs["timeout"] == TIMEOUT


def test_movie_poster_path_none_when_tmdb_has_no_poster(session):
    session.get.return_value = fake_response({"id": 949, "poster_path": None})
    assert TMDBClient("t", session=session).movie_poster_path(949) is None


def test_watch_providers_returns_results_by_country(session):
    session.get.return_value = fake_response(
        {"id": 949, "results": {"GB": {"link": "x"}}}
    )
    client = TMDBClient("t", session=session)
    assert client.watch_providers(949) == {"GB": {"link": "x"}}
    assert session.get.call_args[0][0].endswith("/movie/949/watch/providers")


def test_regions_returns_results(session):
    session.get.return_value = fake_response(
        {"results": [{"iso_3166_1": "GB", "english_name": "United Kingdom"}]}
    )
    assert TMDBClient("t", session=session).regions() == [
        {"iso_3166_1": "GB", "english_name": "United Kingdom"}
    ]


@pytest.mark.parametrize(
    "outcome",
    [
        requests.Timeout("timed out"),
        requests.ConnectionError("refused"),
        fake_response(status=503),
        fake_response(status=401),
        fake_response(json_error=True),
    ],
    ids=["timeout", "connection", "5xx", "4xx", "bad-json"],
)
def test_failures_raise_tmdb_error(session, outcome):
    if isinstance(outcome, Exception):
        session.get.side_effect = outcome
    else:
        session.get.return_value = outcome
    client = TMDBClient("secret-token", session=session)
    for call in (
        lambda: client.watch_providers(949),
        lambda: client.find_movie("tt0113277"),
        lambda: client.movie_poster_path(949),
    ):
        with pytest.raises(TMDBError) as exc:
            call()
        assert "secret-token" not in str(exc.value)


def test_get_client_without_token_raises(settings):
    settings.TMDB_READ_TOKEN = None
    with pytest.raises(TMDBNotConfigured):
        get_tmdb_client()


def test_get_client_with_token(settings):
    settings.TMDB_READ_TOKEN = "abc"
    client = get_tmdb_client()
    assert client.session.headers["Authorization"] == "Bearer abc"


def test_fake_tmdb_fixture_replaces_factory_and_clears_cache(fake_tmdb):
    from movies import tmdb
    from movies.watch import tmdb_cache

    assert tmdb.get_tmdb_client() is fake_tmdb
    fake_tmdb.find["tt1"] = 5
    assert tmdb.get_tmdb_client().find_movie("tt1") == tmdb.TMDBMatch(id=5)
    assert fake_tmdb.count("find") == 1
    assert tmdb_cache().get("anything") is None
