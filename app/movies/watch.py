"""Where a movie can be watched, from TMDB's watch-provider data (JustWatch).

TMDB returns every country in one response, so the raw response is cached per
movie and each request picks its country out of it. Caching the raw data, not
the mapped output, means a mapping fix applies without flushing the cache.
"""

from django.core.cache import caches

from . import tmdb

WATCH_TTL = 24 * 60 * 60
FAILURE_TTL = 60
REGIONS_TTL = 7 * 24 * 60 * 60
REGIONS_KEY = "tmdb:regions"

LOGO_SIZE = "w92"
WATCH_PAGE = "https://www.themoviedb.org/movie/{tmdb_id}/watch"

# TMDB offer type -> our kind, in display order. Free and ad-supported offers
# are a way to stream, so they count as "stream".
KINDS = {
    "flatrate": "stream",
    "free": "stream",
    "ads": "stream",
    "rent": "rent",
    "buy": "buy",
}
KIND_ORDER = ["stream", "rent", "buy"]

FAILED = {"_failed": True}

# The settings.CACHES alias for TMDB data: database-backed, so it's shared by
# every worker and survives restarts.
CACHE_ALIAS = "tmdb"


def tmdb_cache():
    return caches[CACHE_ALIAS]


# Used only when TMDB's regions list can't be fetched and none is cached.
FALLBACK_REGIONS = [
    ("AU", "Australia"),
    ("BR", "Brazil"),
    ("CA", "Canada"),
    ("DK", "Denmark"),
    ("FR", "France"),
    ("DE", "Germany"),
    ("IN", "India"),
    ("IE", "Ireland"),
    ("IT", "Italy"),
    ("JP", "Japan"),
    ("NL", "Netherlands"),
    ("NZ", "New Zealand"),
    ("NO", "Norway"),
    ("ES", "Spain"),
    ("SE", "Sweden"),
    ("GB", "United Kingdom"),
    ("US", "United States of America"),
]


def watch_cache_key(tmdb_id):
    return f"tmdb:watch:{tmdb_id}"


def map_providers(country_data):
    """TMDB's offers for one country -> our provider list, ordered."""
    best = {}
    for offer_type, kind in KINDS.items():
        for provider in country_data.get(offer_type) or []:
            key = (provider["provider_id"], kind)
            priority = provider.get("display_priority", 1_000_000)
            if key not in best or priority < best[key][0]:
                best[key] = (priority, provider)

    def order(item):
        (_, kind), (priority, provider) = item
        return (KIND_ORDER.index(kind), priority, provider.get("provider_name", ""))

    providers = []
    for (provider_id, kind), (_, provider) in sorted(best.items(), key=order):
        logo_path = provider.get("logo_path")
        providers.append(
            {
                "provider_id": provider_id,
                "name": provider.get("provider_name", ""),
                "kind": kind,
                "logo": tmdb.image_url(LOGO_SIZE, logo_path) if logo_path else None,
            }
        )
    return providers


def _watch_results(tmdb_id, client, cache):
    """TMDB's results by country, or None when TMDB can't be reached."""
    key = watch_cache_key(tmdb_id)
    cached = cache.get(key)
    if cached is not None:
        return None if cached == FAILED else cached
    try:
        results = (client or tmdb.get_tmdb_client()).watch_providers(tmdb_id)
    except (tmdb.TMDBError, tmdb.TMDBNotConfigured):
        cache.set(key, FAILED, FAILURE_TTL)
        return None
    cache.set(key, results, WATCH_TTL)
    return results


def watch_options(movie, country, client=None, cache=None):
    """The watch-endpoint body for a movie and an upper-case country code."""
    if cache is None:
        cache = tmdb_cache()
    if movie.tmdb_id is None:
        return {"country": country, "available": False, "link": None, "providers": []}

    fallback_link = WATCH_PAGE.format(tmdb_id=movie.tmdb_id)
    results = _watch_results(movie.tmdb_id, client, cache)
    if results is None:
        return {
            "country": country,
            "available": False,
            "link": fallback_link,
            "providers": [],
        }

    country_data = results.get(country) or {}
    return {
        "country": country,
        "available": True,
        "link": country_data.get("link") or fallback_link,
        "providers": map_providers(country_data),
    }


def regions(client=None, cache=None):
    """[{code, name}] for every country TMDB has watch data for, by name."""
    if cache is None:
        cache = tmdb_cache()
    fallback = [{"code": code, "name": name} for code, name in FALLBACK_REGIONS]
    cached = cache.get(REGIONS_KEY)
    if cached is not None:
        return fallback if cached == FAILED else cached
    try:
        raw = (client or tmdb.get_tmdb_client()).regions()
    except (tmdb.TMDBError, tmdb.TMDBNotConfigured):
        raw = None
    if not raw:
        # Remember the failure briefly, like watch lookups, so an outage
        # doesn't cost a TMDB call (and a blocked worker) per panel open. The
        # fallback itself is never cached as the regions list.
        cache.set(REGIONS_KEY, FAILED, FAILURE_TTL)
        return fallback

    result = sorted(
        (
            {"code": r["iso_3166_1"], "name": r.get("english_name") or r["iso_3166_1"]}
            for r in raw
            if r.get("iso_3166_1")
        ),
        key=lambda r: r["name"],
    )
    cache.set(REGIONS_KEY, result, REGIONS_TTL)
    return result
