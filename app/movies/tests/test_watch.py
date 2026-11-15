import pytest

from movies import watch
from movies.watch import tmdb_cache
from movies.tmdb import get_tmdb_client as real_get_tmdb_client

from .factories import MovieFactory

GB_LINK = "https://www.themoviedb.org/movie/949-heat/watch?locale=GB"


def provider(pid, name, priority=1, logo="/logo.png"):
    return {
        "provider_id": pid,
        "provider_name": name,
        "display_priority": priority,
        "logo_path": logo,
    }


@pytest.fixture
def heat(fake_tmdb):
    movie = MovieFactory(imdbid="tt0113277", title="Heat", tmdb_id=949)
    fake_tmdb.watch[949] = {
        "GB": {
            "link": GB_LINK,
            "flatrate": [provider(8, "Netflix", 2), provider(9, "Prime Video", 1)],
            "rent": [provider(2, "Apple TV", 5)],
            "buy": [provider(2, "Apple TV", 5), provider(10, "Amazon Video", 4)],
        },
        "US": {"link": "https://example.test/us", "ads": [provider(300, "Pluto")]},
    }
    return movie


class RecordingCache:
    """Wraps the real cache and records the timeout of every set()."""

    def __init__(self):
        self.timeouts = {}

    def get(self, key):
        return tmdb_cache().get(key)

    def set(self, key, value, timeout):
        self.timeouts[key] = timeout
        tmdb_cache().set(key, value, timeout)


def test_kinds_order_and_shape(heat):
    body = watch.watch_options(heat, "GB")

    assert body["country"] == "GB"
    assert body["available"] is True
    assert body["link"] == GB_LINK
    assert [(p["name"], p["kind"]) for p in body["providers"]] == [
        ("Prime Video", "stream"),
        ("Netflix", "stream"),
        ("Apple TV", "rent"),
        ("Amazon Video", "buy"),
        ("Apple TV", "buy"),
    ]
    assert body["providers"][0] == {
        "provider_id": 9,
        "name": "Prime Video",
        "kind": "stream",
        "logo": "https://image.tmdb.org/t/p/w92/logo.png",
    }


@pytest.mark.parametrize("offer_type", ["free", "ads", "flatrate"])
def test_free_and_ad_supported_count_as_stream(fake_tmdb, offer_type):
    movie = MovieFactory(tmdb_id=1)
    fake_tmdb.watch[1] = {"GB": {"link": "x", offer_type: [provider(300, "Pluto")]}}

    [entry] = watch.watch_options(movie, "GB")["providers"]
    assert entry["kind"] == "stream"


def test_same_provider_twice_in_one_kind_is_one_entry(fake_tmdb):
    movie = MovieFactory(tmdb_id=1)
    fake_tmdb.watch[1] = {
        "GB": {
            "link": "x",
            "free": [provider(300, "Pluto", 9)],
            "flatrate": [provider(300, "Pluto", 3)],
        }
    }
    assert watch.watch_options(movie, "GB")["providers"] == [
        {
            "provider_id": 300,
            "name": "Pluto",
            "kind": "stream",
            "logo": "https://image.tmdb.org/t/p/w92/logo.png",
        }
    ]


def test_missing_logo_is_null(fake_tmdb):
    movie = MovieFactory(tmdb_id=1)
    fake_tmdb.watch[1] = {"GB": {"link": "x", "buy": [provider(5, "Shop", logo=None)]}}
    assert watch.watch_options(movie, "GB")["providers"][0]["logo"] is None


def test_country_without_data_gets_empty_list_and_fallback_link(heat):
    body = watch.watch_options(heat, "MN")
    assert body == {
        "country": "MN",
        "available": True,
        "link": "https://www.themoviedb.org/movie/949/watch",
        "providers": [],
    }


def test_country_entry_without_link_falls_back(fake_tmdb):
    movie = MovieFactory(tmdb_id=1)
    fake_tmdb.watch[1] = {"GB": {"buy": [provider(5, "Shop")]}}
    assert (
        watch.watch_options(movie, "GB")["link"]
        == "https://www.themoviedb.org/movie/1/watch"
    )


def test_one_tmdb_call_serves_every_country_for_24h(heat):
    recording = RecordingCache()
    watch.watch_options(heat, "GB", cache=recording)
    watch.watch_options(heat, "US", cache=recording)

    assert watch.tmdb.get_tmdb_client().count("watch") == 1
    assert recording.timeouts == {"tmdb:watch:949": 24 * 60 * 60}


def test_movie_without_tmdb_id_never_calls_tmdb(fake_tmdb):
    movie = MovieFactory(tmdb_id=None)
    assert watch.watch_options(movie, "GB") == {
        "country": "GB",
        "available": False,
        "link": None,
        "providers": [],
    }
    assert fake_tmdb.calls == []


def test_tmdb_down_is_unavailable_and_cached_for_60s_only(heat, fake_tmdb):
    fake_tmdb.fail = True
    recording = RecordingCache()

    for _ in range(3):
        body = watch.watch_options(heat, "GB", cache=recording)
    assert body == {
        "country": "GB",
        "available": False,
        "link": "https://www.themoviedb.org/movie/949/watch",
        "providers": [],
    }
    assert fake_tmdb.count("watch") == 1
    assert recording.timeouts == {"tmdb:watch:949": 60}


def test_recovers_once_failure_marker_expires(heat, fake_tmdb):
    fake_tmdb.fail = True
    watch.watch_options(heat, "GB")
    fake_tmdb.fail = False
    tmdb_cache().delete(watch.watch_cache_key(949))  # what the 60 s expiry does

    assert watch.watch_options(heat, "GB")["available"] is True
    assert fake_tmdb.count("watch") == 2


def test_missing_token_is_treated_as_unavailable(heat, monkeypatch, settings):
    monkeypatch.setattr(watch.tmdb, "get_tmdb_client", real_get_tmdb_client)
    settings.TMDB_READ_TOKEN = None
    assert watch.watch_options(heat, "GB")["available"] is False


def test_regions_sorted_by_name_and_cached_for_a_week(fake_tmdb):
    fake_tmdb.region_list = [
        {"iso_3166_1": "US", "english_name": "United States of America"},
        {"iso_3166_1": "GB", "english_name": "United Kingdom"},
        {"iso_3166_1": "DE", "english_name": "Germany"},
    ]
    recording = RecordingCache()

    first = watch.regions(cache=recording)
    second = watch.regions(cache=recording)
    assert (
        first
        == second
        == [
            {"code": "DE", "name": "Germany"},
            {"code": "GB", "name": "United Kingdom"},
            {"code": "US", "name": "United States of America"},
        ]
    )
    assert fake_tmdb.count("regions") == 1
    assert recording.timeouts == {"tmdb:regions": 7 * 24 * 60 * 60}


def test_regions_fall_back_when_tmdb_down_and_remember_failure_for_60s(fake_tmdb):
    fake_tmdb.fail = True
    recording = RecordingCache()

    result = watch.regions(cache=recording)
    codes = [r["code"] for r in result]
    assert {"GB", "US"} <= set(codes)
    assert [r["name"] for r in result] == sorted(r["name"] for r in result)
    # Only a short failure marker is stored, never the fallback as the list.
    assert recording.timeouts == {"tmdb:regions": 60}

    # Within the 60 s, repeat requests get the fallback without calling TMDB.
    assert watch.regions(cache=recording) == result
    assert fake_tmdb.count("regions") == 1

    fake_tmdb.fail = False
    fake_tmdb.region_list = [{"iso_3166_1": "GB", "english_name": "United Kingdom"}]
    tmdb_cache().delete("tmdb:regions")  # what the 60 s expiry does
    assert watch.regions() == [{"code": "GB", "name": "United Kingdom"}]
    assert fake_tmdb.count("regions") == 2


def test_tmdb_data_uses_a_shared_db_cache_not_the_default(settings):
    # The default cache backs DRF throttling on every request, so it must not
    # be the database cache (extra queries per request, shared cull limit).
    assert (
        settings.CACHES[watch.CACHE_ALIAS]["BACKEND"]
        == "django.core.cache.backends.db.DatabaseCache"
    )
    assert "DatabaseCache" not in settings.CACHES["default"]["BACKEND"]
