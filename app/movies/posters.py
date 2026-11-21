"""Check every stored TMDB poster path still loads, and repair the ones that
don't.

Phase 1 sends a HEAD request for each stored path's w342 image, four at a
time, and makes no TMDB API calls. Phase 2 re-reads, one at a time, every
movie whose image is broken and every mapped movie with no path yet, and
stores the path TMDB gives now. A failed check never clears a path by
itself.

Called by the check_posters management command (by hand, anywhere the API
runs) and by the weekly movies.tasks.check_posters Celery task.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

import requests
from django.db.models import Q

from . import tmdb
from .models import Movie

logger = logging.getLogger(__name__)

IMAGE_BASE = "https://image.tmdb.org/t/p/w342"
DEFAULT_SLEEP = 0.05
WORKERS = 4
HEAD_TIMEOUT = 5
ATTEMPTS = 3
BACKOFF = (0.5, 1)
MAX_BROKEN_SHARE = 0.05


def image_url(poster_path):
    return f"{IMAGE_BASE}{poster_path}"


@dataclass(frozen=True)
class PosterCheckResult:
    checked: int
    fixed: int
    missing: int
    broken: int

    @property
    def over_threshold(self):
        return self.checked > 0 and self.broken / self.checked > MAX_BROKEN_SHARE

    def as_dict(self):
        return asdict(self)

    def __str__(self):
        return (
            f"checked={self.checked} fixed={self.fixed} "
            f"missing={self.missing} broken={self.broken}"
        )


class PosterCheckFailed(Exception):
    """More than 5% of poster images were still broken after repair."""


_sessions = threading.local()


def _session():
    # One Session per thread: requests doesn't document Session as
    # thread-safe.
    if not hasattr(_sessions, "session"):
        _sessions.session = requests.Session()
    return _sessions.session


def _retryable(status):
    return status == 429 or status >= 500


def head(url):
    """True when the image at url loads.

    Connection errors, timeouts, 429 and 5xx are retried, up to ATTEMPTS
    tries in all. Any other answer is final; success is a 2xx.
    """
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(BACKOFF[attempt - 1])
        try:
            status = (
                _session()
                .head(url, allow_redirects=True, timeout=HEAD_TIMEOUT)
                .status_code
            )
        except requests.RequestException:
            continue
        if not _retryable(status):
            return 200 <= status < 300
    return False


def _no_path():
    return Q(poster_path__isnull=True) | Q(poster_path="")


def check_posters(head=head, client=None, sleep=DEFAULT_SLEEP):
    """Check and repair poster paths. Returns a PosterCheckResult.

    Raises tmdb.TMDBNotConfigured before making any request when no token
    is set. Doesn't raise for the 5% rule: callers read over_threshold.
    """
    if client is None:
        client = tmdb.get_tmdb_client()

    with_path = list(
        Movie.objects.exclude(_no_path())
        .order_by("imdbid")
        .values_list("imdbid", "tmdb_id", "poster_path")
    )
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        loads = list(pool.map(lambda row: head(image_url(row[2])), with_path))
    broken_rows = [row for row, ok in zip(with_path, loads) if not ok]

    pathless_rows = list(
        Movie.objects.filter(_no_path(), tmdb_id__isnull=False)
        .order_by("imdbid")
        .values_list("imdbid", "tmdb_id", "poster_path")
    )

    fixed = broken = 0
    for i, (imdbid, tmdb_id, old_path) in enumerate(broken_rows + pathless_rows):
        was_broken = bool(old_path)
        if tmdb_id is None:
            # A broken path on an unmapped movie: nothing to ask TMDB.
            broken += 1
            continue
        if i and sleep:
            time.sleep(sleep)
        try:
            new_path = client.movie_poster_path(tmdb_id)
        except tmdb.TMDBError as e:
            logger.warning("TMDB poster lookup failed for %s: %s", imdbid, e)
            broken += was_broken
            continue
        if new_path is None:
            logger.info("TMDB has no poster for %s", imdbid)
            Movie.objects.filter(pk=imdbid).update(poster_path=None)
            continue
        if new_path == old_path:
            logger.warning("TMDB still gives broken poster %s for %s", new_path, imdbid)
            broken += 1
            continue
        Movie.objects.filter(pk=imdbid).update(poster_path=new_path)
        if head(image_url(new_path)):
            fixed += 1
        else:
            logger.warning("New poster %s for %s does not load", new_path, imdbid)
            broken += 1

    missing = Movie.objects.filter(_no_path()).count()
    return PosterCheckResult(
        checked=len(with_path), fixed=fixed, missing=missing, broken=broken
    )
