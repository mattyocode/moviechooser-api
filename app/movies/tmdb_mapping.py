"""Link catalogue movies to TMDB movie IDs.

Idempotent: only movies with no tmdb_id are looked up, so a re-run after a
full success makes no requests, and unmatched movies are retried next time.
Called by the map_tmdb_ids management command (by hand, anywhere the API
runs) and by the daily movies.tasks.map_tmdb_ids Celery task.
"""

import logging
import time
from dataclasses import asdict, dataclass

from . import tmdb
from .models import Movie

logger = logging.getLogger(__name__)

DEFAULT_SLEEP = 0.05


@dataclass(frozen=True)
class MappingResult:
    mapped: int
    unmatched: int
    failed: int

    def as_dict(self):
        return asdict(self)

    def __str__(self):
        return f"mapped={self.mapped} unmatched={self.unmatched} failed={self.failed}"


def map_tmdb_ids(limit=None, sleep=DEFAULT_SLEEP, client=None):
    """Look up a TMDB movie ID for every movie that doesn't have one.

    Raises tmdb.TMDBNotConfigured before touching anything when no token is
    set. A failed lookup is logged and counted, and the run carries on.
    """
    if client is None:
        client = tmdb.get_tmdb_client()

    movies = Movie.objects.filter(tmdb_id__isnull=True).order_by("imdbid")
    if limit is not None:
        movies = movies[: max(limit, 0)]

    mapped = unmatched = failed = 0
    for i, movie in enumerate(movies.only("imdbid", "title", "tmdb_id")):
        if i and sleep:
            time.sleep(sleep)
        try:
            tmdb_id = client.find_movie_id(movie.imdbid)
        except tmdb.TMDBError as e:
            failed += 1
            logger.warning("TMDB lookup failed for %s: %s", movie.imdbid, e)
            continue
        if tmdb_id is None:
            unmatched += 1
            logger.info("No TMDB movie for %s (%s)", movie.imdbid, movie.title)
            continue
        movie.tmdb_id = tmdb_id
        movie.save(update_fields=["tmdb_id"])
        mapped += 1

    return MappingResult(mapped=mapped, unmatched=unmatched, failed=failed)
