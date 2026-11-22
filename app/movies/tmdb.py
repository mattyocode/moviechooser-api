"""A small TMDB API client.

Views and the map_tmdb_ids command get a client only through
get_tmdb_client(), so tests can swap in a fake and CI never touches the
network.
"""

from dataclasses import dataclass

import requests
from django.conf import settings

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT = 3
IMAGE_BASE = "https://image.tmdb.org/t/p"


def image_url(size, path):
    """The URL of a TMDB image path such as "/abc123.jpg" at a size such as
    "w342"."""
    return f"{IMAGE_BASE}/{size}{path}"


class TMDBError(Exception):
    """A TMDB request failed: network error, timeout, error status or bad JSON."""


class TMDBNotConfigured(Exception):
    """No TMDB token is configured."""


@dataclass(frozen=True)
class TMDBMatch:
    """A TMDB movie found by IMDb ID: its ID and poster path (or None)."""

    id: int
    poster_path: str | None = None


class TMDBClient:
    def __init__(self, token, session=None):
        self.session = session or requests.Session()
        # A header, not the v3 ?api_key=, so the credential never ends up in
        # URLs, access logs or exception messages.
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        )

    def close(self):
        self.session.close()

    def _get(self, path, params=None):
        try:
            response = self.session.get(
                f"{BASE_URL}{path}", params=params, timeout=TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            # Name the path only: str(e) can carry the full request.
            raise TMDBError(f"TMDB request to {path} failed: {type(e).__name__}")
        except ValueError:
            raise TMDBError(f"TMDB returned invalid JSON for {path}")

    def find_movie(self, imdbid):
        """The TMDB movie for an IMDb ID as a TMDBMatch, or None when TMDB has
        no movie.

        TV results are ignored: the catalogue is movies.
        """
        data = self._get(f"/find/{imdbid}", params={"external_source": "imdb_id"})
        results = data.get("movie_results") or []
        if not results:
            return None
        first = results[0]
        return TMDBMatch(id=first["id"], poster_path=first.get("poster_path") or None)

    def movie_poster_path(self, tmdb_id):
        """The poster path TMDB currently gives a movie, or None if it has none."""
        data = self._get(f"/movie/{tmdb_id}")
        return data.get("poster_path") or None

    def watch_providers(self, tmdb_id):
        """TMDB's watch-provider results for a movie, keyed by country code."""
        data = self._get(f"/movie/{tmdb_id}/watch/providers")
        return data.get("results") or {}

    def regions(self):
        """The countries TMDB has watch-provider data for."""
        data = self._get("/watch/providers/regions")
        return data.get("results") or []


def get_tmdb_client():
    token = settings.TMDB_READ_TOKEN
    if not token:
        raise TMDBNotConfigured("TMDB_READ_TOKEN is not set")
    return TMDBClient(token)
