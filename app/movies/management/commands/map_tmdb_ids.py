"""Link catalogue movies to TMDB movie IDs.

Idempotent: only movies with no tmdb_id are looked up, so a re-run after a
full success makes no requests, and unmatched movies are retried next time.
Runs anywhere the API runs (laptop or server) and daily via Celery beat.
"""

import logging
import time

from django.core.management.base import BaseCommand, CommandError

from movies import tmdb
from movies.models import Movie

logger = logging.getLogger(__name__)


def non_negative_float(value):
    number = float(value)
    if number < 0:
        raise ValueError("must be >= 0")
    return number


class Command(BaseCommand):
    help = "Look up a TMDB movie ID for every movie that doesn't have one."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None, help="Look up at most N movies."
        )
        parser.add_argument(
            "--sleep",
            type=non_negative_float,
            default=0.05,
            help="Seconds to wait between TMDB requests (default 0.05).",
        )

    def handle(self, *args, limit=None, sleep=0.05, **options):
        try:
            client = tmdb.get_tmdb_client()
        except tmdb.TMDBNotConfigured as e:
            raise CommandError(f"{e}. Set TMDB_READ_TOKEN to run map_tmdb_ids.")

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

        self.stdout.write(f"mapped={mapped} unmatched={unmatched} failed={failed}")
