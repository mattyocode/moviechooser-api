"""Link catalogue movies to TMDB movie IDs, by hand.

The work is done by movies.tmdb_mapping.map_tmdb_ids, which the daily Celery
task also calls. This command only parses options, turns a missing token
into a CommandError, and prints the summary.
"""

from django.core.management.base import BaseCommand, CommandError

from movies import tmdb
from movies.tmdb_mapping import DEFAULT_SLEEP, map_tmdb_ids


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
            default=DEFAULT_SLEEP,
            help=f"Seconds to wait between TMDB requests (default {DEFAULT_SLEEP}).",
        )

    def handle(self, *args, limit=None, sleep=DEFAULT_SLEEP, **options):
        try:
            result = map_tmdb_ids(limit=limit, sleep=sleep)
        except tmdb.TMDBNotConfigured as e:
            raise CommandError(f"{e}. Set TMDB_READ_TOKEN to run map_tmdb_ids.")
        self.stdout.write(str(result))
