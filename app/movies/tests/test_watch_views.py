import json

import pytest

from .factories import MovieFactory

GB_LINK = "https://www.themoviedb.org/movie/949-heat/watch?locale=GB"
TOKEN = "super-secret-tmdb-token"


@pytest.fixture
def heat(fake_tmdb, settings):
    settings.TMDB_READ_TOKEN = TOKEN
    movie = MovieFactory(imdbid="tt0113277", title="Heat", tmdb_id=949)
    fake_tmdb.watch[949] = {
        "GB": {
            "link": GB_LINK,
            "flatrate": [
                {
                    "provider_id": 8,
                    "provider_name": "Netflix",
                    "display_priority": 1,
                    "logo_path": "/n.png",
                }
            ],
        },
        "DE": {"link": "https://example.test/de", "buy": []},
    }
    return movie


def url(movie, query=""):
    return f"/api/movies/{movie.slug}/watch/{query}"


def test_known_movie_shape(client, heat):
    resp = client.get(url(heat, "?country=GB"))
    assert resp.status_code == 200
    assert resp.json() == {
        "country": "GB",
        "available": True,
        "link": GB_LINK,
        "providers": [
            {
                "provider_id": 8,
                "name": "Netflix",
                "kind": "stream",
                "logo": "https://image.tmdb.org/t/p/w92/n.png",
            }
        ],
    }


def test_signed_in_client_also_gets_200(heat, auth_user_client):
    assert auth_user_client.get(url(heat)).status_code == 200


def test_unknown_slug_is_404(client, fake_tmdb):
    assert client.get("/api/movies/no-such-movie/watch/").status_code == 404


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_write_methods_are_405(client, heat, method):
    assert getattr(client, method)(url(heat)).status_code == 405


def test_lower_case_country_is_upper_cased(client, heat):
    body = client.get(url(heat, "?country=de")).json()
    assert body["country"] == "DE"
    assert body["link"] == "https://example.test/de"


@pytest.mark.parametrize("query", ["", "?country=", "?country=%20"])
def test_missing_country_defaults_to_gb(client, heat, query):
    assert client.get(url(heat, query)).json()["country"] == "GB"


@pytest.mark.parametrize("country", ["GBR", "1x", "g", "G-"])
def test_malformed_country_is_400_without_calling_tmdb(
    client, heat, fake_tmdb, country
):
    resp = client.get(url(heat, f"?country={country}"))
    assert resp.status_code == 400
    assert "country" in resp.json()["error"]
    assert fake_tmdb.calls == []


def test_valid_country_with_no_data(client, heat):
    assert client.get(url(heat, "?country=MN")).json() == {
        "country": "MN",
        "available": True,
        "link": "https://www.themoviedb.org/movie/949/watch",
        "providers": [],
    }


def test_tmdb_down_is_200_unavailable(client, heat, fake_tmdb):
    fake_tmdb.fail = True
    resp = client.get(url(heat))
    assert resp.status_code == 200
    assert resp.json() == {
        "country": "GB",
        "available": False,
        "link": "https://www.themoviedb.org/movie/949/watch",
        "providers": [],
    }


def test_movie_without_tmdb_id_does_not_call_tmdb(client, fake_tmdb):
    movie = MovieFactory(tmdb_id=None)
    resp = client.get(url(movie))
    assert resp.status_code == 200
    assert resp.json() == {
        "country": "GB",
        "available": False,
        "link": None,
        "providers": [],
    }
    assert fake_tmdb.calls == []


def test_second_country_is_served_from_cache(client, heat, fake_tmdb):
    client.get(url(heat, "?country=GB"))
    client.get(url(heat, "?country=US"))
    assert fake_tmdb.count("watch") == 1


def test_regions_endpoint(client, fake_tmdb):
    fake_tmdb.region_list = [
        {"iso_3166_1": "US", "english_name": "United States of America"},
        {"iso_3166_1": "GB", "english_name": "United Kingdom"},
    ]
    resp = client.get("/api/watch/regions/")
    assert resp.status_code == 200
    assert {"code": "GB", "name": "United Kingdom"} in resp.json()


def test_regions_endpoint_falls_back_when_tmdb_down(client, fake_tmdb):
    fake_tmdb.fail = True
    resp = client.get("/api/watch/regions/")
    assert resp.status_code == 200
    codes = {r["code"] for r in resp.json()}
    assert {"GB", "US"} <= codes


def test_token_never_appears_in_responses(client, heat, fake_tmdb):
    bodies = [
        client.get(url(heat, "?country=GB")).content,
        client.get(url(heat, "?country=MN")).content,
        client.get("/api/watch/regions/").content,
    ]
    fake_tmdb.fail = True
    other = MovieFactory(tmdb_id=1)
    bodies.append(client.get(url(other)).content)
    for body in bodies:
        assert TOKEN not in body.decode()
        json.loads(body)
