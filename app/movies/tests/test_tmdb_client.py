from unittest import mock

import pytest
import requests

from movies.tmdb import (
    TIMEOUT,
    TMDBClient,
    TMDBError,
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
    TMDBClient("secret-token", session=session).find_movie_id("tt0113277")

    assert session.headers["Authorization"] == "Bearer secret-token"
    args, kwargs = session.get.call_args
    assert "secret-token" not in args[0]
    assert "secret-token" not in str(kwargs.get("params"))


def test_find_uses_imdb_external_source_and_timeout(session):
    session.get.return_value = fake_response({"movie_results": []})
    TMDBClient("t", session=session).find_movie_id("tt0113277")

    args, kwargs = session.get.call_args
    assert args[0] == "https://api.themoviedb.org/3/find/tt0113277"
    assert kwargs["params"] == {"external_source": "imdb_id"}
    assert kwargs["timeout"] == TIMEOUT == 3


def test_find_returns_first_movie_result(session):
    session.get.return_value = fake_response(
        {"movie_results": [{"id": 949}, {"id": 1}], "tv_results": []}
    )
    assert TMDBClient("t", session=session).find_movie_id("tt0113277") == 949


def test_find_ignores_tv_results(session):
    session.get.return_value = fake_response(
        {"movie_results": [], "tv_results": [{"id": 1399}]}
    )
    assert TMDBClient("t", session=session).find_movie_id("tt0944947") is None


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
    with pytest.raises(TMDBError) as exc:
        TMDBClient("secret-token", session=session).watch_providers(949)
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
    from django.core.cache import cache

    from movies import tmdb

    assert tmdb.get_tmdb_client() is fake_tmdb
    fake_tmdb.find["tt1"] = 5
    assert tmdb.get_tmdb_client().find_movie_id("tt1") == 5
    assert fake_tmdb.count("find") == 1
    assert cache.get("anything") is None
