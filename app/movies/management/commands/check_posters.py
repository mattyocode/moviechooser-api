"""Check and repair TMDB poster paths, by hand.

The work is done by movies.posters.check_posters, which the weekly Celery
task also calls. This command only parses options, turns a missing token
into a CommandError, prints the summary, and fails when the result has a
problem (too many posters still broken).
"""

from django.core.management.base import BaseCommand, CommandError

from movies import tmdb
from movies.management.args import non_negative_float
from movies.posters import DEFAULT_SLEEP, check_posters


class Command(BaseCommand):
    help = (
        "Check every stored TMDB poster loads; re-read broken and missing "
        "ones from TMDB."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sleep",
            type=non_negative_float,
            default=DEFAULT_SLEEP,
            help=(
                "Seconds each worker waits before a TMDB request "
                f"(default {DEFAULT_SLEEP})."
            ),
        )

    def handle(self, *args, sleep=DEFAULT_SLEEP, **options):
        try:
            result = check_posters(sleep=sleep)
        except tmdb.TMDBNotConfigured as e:
            raise CommandError(f"{e}. Set TMDB_READ_TOKEN to run check_posters.")
        self.stdout.write(str(result))
        if problem := result.problem():
            raise CommandError(problem)
