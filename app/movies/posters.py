"""Check every stored TMDB poster path still loads, and repair the ones that
don't.

Phase 1 sends a HEAD request for each stored path's w342 image and makes no
TMDB API calls. Phase 2 re-reads from TMDB every movie whose image is broken
and every mapped movie with no path yet (skipping ones TMDB recently said
have no poster), then checks the image it gives. Both phases run WORKERS at
a time; only the main thread touches the database. A failed check never
clears a path by itself, and a movie changed while the run is going is left
alone.

Called by the check_posters management command (by hand, anywhere the API
runs) and by the weekly movies.tasks.check_posters Celery task, which passes
a time budget so the run stops cleanly before Celery kills it.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import timedelta

import requests
from django.db.models import Q
from django.utils import timezone

from . import tmdb
from .models import Movie

logger = logging.getLogger(__name__)

IMAGE_SIZE = "w342"
DEFAULT_SLEEP = 0.05
WORKERS = 4
HEAD_TIMEOUT = 5
ATTEMPTS = 3
BACKOFF = (0.5, 1)
MAX_BROKEN_SHARE = 0.05
# How long to trust TMDB's "no poster" before asking about that movie again.
NO_POSTER_RECHECK = timedelta(days=90)

# Makes every HTTP session this module uses; tests swap in a fake.
_new_session = requests.Session


def image_url(poster_path):
    return tmdb.image_url(IMAGE_SIZE, poster_path)


@dataclass(frozen=True)
class PosterCheckResult:
    """checked: movies whose image was checked, in either phase. fixed: new
    paths stored that load. missing: movies with no path at the end.
    broken: checked movies whose image still doesn't load. complete: False
    when the time budget ran out first."""

    checked: int
    fixed: int
    missing: int
    broken: int
    complete: bool = True

    def problem(self):
        """Why this run should fail, as a message, or None when it's fine."""
        if not self.complete:
            return f"Ran out of time before checking every poster: {self}"
        if self.checked and self.broken / self.checked > MAX_BROKEN_SHARE:
            return f"More than {MAX_BROKEN_SHARE:.0%} of posters still broken: {self}"
        return None

    def as_dict(self):
        return asdict(self)

    def __str__(self):
        summary = (
            f"checked={self.checked} fixed={self.fixed} "
            f"missing={self.missing} broken={self.broken}"
        )
        return summary if self.complete else f"{summary} incomplete"


class PosterCheckFailed(Exception):
    """A poster check found too many broken images or didn't finish; the
    message is PosterCheckResult.problem()."""


class _PerThread:
    """One object per thread, made by factory() on first use. Used as a
    context manager, it closes every object it made on exit. (requests
    doesn't document Session as thread-safe, so threads don't share one.)"""

    def __init__(self, factory):
        self._factory = factory
        self._local = threading.local()
        self._made = []
        self._lock = threading.Lock()

    def get(self):
        obj = getattr(self._local, "obj", None)
        if obj is None:
            obj = self._local.obj = self._factory()
            with self._lock:
                self._made.append(obj)
        return obj

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for obj in self._made:
            obj.close()


def _retryable(status):
    return status == 429 or status >= 500


def head(url, session=None):
    """True when the image at url loads.

    Connection errors, timeouts, 429 and 5xx are retried, up to ATTEMPTS
    tries in all. Any other answer is final; success is a 2xx. Without a
    session, it uses (and closes) one of its own.
    """
    if session is None:
        with _new_session() as own:
            return head(url, own)
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(BACKOFF[attempt - 1])
        try:
            status = session.head(
                url, allow_redirects=True, timeout=HEAD_TIMEOUT
            ).status_code
        except requests.RequestException:
            continue
        if not _retryable(status):
            return 200 <= status < 300
    return False


# What phase 2 found for one movie.
SKIPPED = "skipped"  # out of time, not looked up
LOOKUP_FAILED = "lookup_failed"
NO_POSTER = "no_poster"
SAME_LOADS = "same_loads"  # TMDB gave the stored path, and it loads now
SAME_BROKEN = "same_broken"
NEW_LOADS = "new_loads"
NEW_BROKEN = "new_broken"


def _store(imdbid, tmdb_id, old_path, **fields):
    """Update a movie only if its tmdb_id and path are still what this run
    read, so a change made while the run was going wins. True if updated."""
    updated = Movie.objects.filter(
        pk=imdbid, tmdb_id=tmdb_id, poster_path=old_path
    ).update(**fields)
    if not updated:
        logger.info("%s changed during the poster check; left alone", imdbid)
    return bool(updated)


def check_posters(client_factory=None, sleep=DEFAULT_SLEEP, time_budget=None):
    """Check and repair poster paths. Returns a PosterCheckResult.

    client_factory makes a TMDB client per worker thread (default
    tmdb.get_tmdb_client). sleep is the pause before each TMDB request, per
    worker. time_budget, in seconds, stops new work once it has passed; the
    result is then incomplete.

    Raises tmdb.TMDBNotConfigured before making any request when no token
    is set. Doesn't raise for a failed run: callers read problem().
    """
    if client_factory is None:
        client_factory = tmdb.get_tmdb_client
    client_factory().close()  # raises TMDBNotConfigured before any request

    deadline = None if time_budget is None else time.monotonic() + time_budget

    def out_of_time():
        return deadline is not None and time.monotonic() >= deadline

    with (
        _PerThread(_new_session) as sessions,
        _PerThread(client_factory) as clients,
        ThreadPoolExecutor(max_workers=WORKERS) as pool,
    ):

        def loads(path):
            return head(image_url(path), sessions.get())

        def check(row):
            return None if out_of_time() else loads(row[2])

        def lookup(row):
            imdbid, tmdb_id, old_path = row
            if out_of_time():
                return SKIPPED, None
            if sleep:
                time.sleep(sleep)
            try:
                new_path = clients.get().movie_poster_path(tmdb_id)
            except tmdb.TMDBError as e:
                logger.warning("TMDB poster lookup failed for %s: %s", imdbid, e)
                return LOOKUP_FAILED, None
            if new_path is None:
                return NO_POSTER, None
            if new_path == old_path:
                # Phase 1 may have hit a passing outage: check once more.
                return (SAME_LOADS if loads(new_path) else SAME_BROKEN), new_path
            return (NEW_LOADS if loads(new_path) else NEW_BROKEN), new_path

        with_path = list(
            Movie.objects.filter(poster_path__isnull=False)
            .order_by("imdbid")
            .values_list("imdbid", "tmdb_id", "poster_path")
        )
        checks = list(pool.map(check, with_path))
        complete = None not in checks
        checked = sum(ok is not None for ok in checks)
        broken_rows = [row for row, ok in zip(with_path, checks) if ok is False]

        # A broken path on an unmapped movie: nothing to ask TMDB.
        broken = sum(tmdb_id is None for _, tmdb_id, _ in broken_rows)
        to_lookup = [row for row in broken_rows if row[1] is not None]
        recheck_before = timezone.now() - NO_POSTER_RECHECK
        to_lookup += list(
            Movie.objects.filter(poster_path__isnull=True, tmdb_id__isnull=False)
            .filter(
                Q(no_poster_checked_at__isnull=True)
                | Q(no_poster_checked_at__lt=recheck_before)
            )
            .order_by("imdbid")
            .values_list("imdbid", "tmdb_id", "poster_path")
        )
        found = list(pool.map(lookup, to_lookup))

    fixed = 0
    for (imdbid, tmdb_id, old_path), (outcome, new_path) in zip(to_lookup, found):
        was_broken = old_path is not None
        if outcome == SKIPPED:
            complete = False
            broken += was_broken
        elif outcome == LOOKUP_FAILED:
            broken += was_broken
        elif outcome == NO_POSTER:
            logger.info("TMDB has no poster for %s", imdbid)
            _store(
                imdbid,
                tmdb_id,
                old_path,
                poster_path=None,
                no_poster_checked_at=timezone.now(),
            )
        elif outcome == SAME_LOADS:
            logger.info("Poster for %s loads on a second check", imdbid)
        elif outcome == SAME_BROKEN:
            logger.warning("TMDB still gives broken poster %s for %s", new_path, imdbid)
            broken += 1
        elif _store(
            imdbid,
            tmdb_id,
            old_path,
            poster_path=new_path,
            no_poster_checked_at=None,
        ):
            checked += not was_broken
            if outcome == NEW_LOADS:
                fixed += 1
            else:
                logger.warning("New poster %s for %s does not load", new_path, imdbid)
                broken += 1

    missing = Movie.objects.filter(poster_path__isnull=True).count()
    return PosterCheckResult(
        checked=checked, fixed=fixed, missing=missing, broken=broken, complete=complete
    )
