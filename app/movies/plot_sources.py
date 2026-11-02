"""Plot text from English Wikipedia (via Wikidata's IMDb ID property) and OMDb."""

import hashlib
import json
import logging
import os
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
ENWIKI_API_URL = "https://en.wikipedia.org/w/api.php"
ENWIKI_ARTICLE_URL = "https://en.wikipedia.org/wiki/{title}"
OMDB_URL = "https://www.omdbapi.com/"
IMDB_TITLE_URL = "https://www.imdb.com/title/{imdbid}/"

SPARQL_BATCH_SIZE = 500
TITLES_PER_REQUEST = 50
# Fiction uses plot-like headings; documentaries describe their subject instead.
PLOT_HEADINGS = {
    "plot",
    "plot summary",
    "plot and background",
    "synopsis",
    "premise",
    "story",
    "storyline",
    "storylines",
    "summary",
    "overview",
    "content",
    "description",
    "subject",
    "subject matter",
}
MIN_PLOT_WORDS = 30
# Transient failures worth retrying. MediaWiki reports some of them in a 200 body.
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_API_ERRORS = {"maxlag", "ratelimited"}
# A server asking for a longer wait is treated as down rather than waited on.
MAX_RETRY_AFTER = 120
IMDB_ID = re.compile(r"tt\d+")


class PlotSourceError(Exception):
    pass


class PoliteClient:
    """Serial HTTP client that spaces requests out and backs off when asked to."""

    def __init__(
        self,
        session,
        min_interval=1.0,
        max_tries=5,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.session = session
        self.min_interval = min_interval
        self.max_tries = max_tries
        self.sleep = sleep
        self.clock = clock
        self._last = None

    def request_json(self, method, url, **kwargs):
        """The decoded JSON body, retrying transient failures.

        Errors name only `url`, never the query parameters, which can hold an
        API key: requests' own messages include the full URL.
        """
        for attempt in range(self.max_tries):
            if self._last is not None:
                wait = self.min_interval - (self.clock() - self._last)
                if wait > 0:
                    self.sleep(wait)
            try:
                response = self.session.request(method, url, timeout=60, **kwargs)
            except (
                requests.ConnectionError,
                requests.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ) as e:
                self._last = self.clock()
                problem, retry_after = type(e).__name__, 2**attempt
            else:
                self._last = self.clock()
                status = response.status_code
                if status in RETRY_STATUSES:
                    problem = f"HTTP {status}"
                    retry_after = retry_after_seconds(response, 2**attempt)
                elif status >= 400:
                    raise PlotSourceError(f"HTTP {status} from {url}")
                else:
                    try:
                        data = response.json()
                    except ValueError:
                        # A body cut off mid-stream, e.g. a query service timeout.
                        problem, retry_after = "Invalid JSON", 2**attempt
                    else:
                        error = data.get("error") if isinstance(data, dict) else None
                        if not error:
                            return data
                        code = error.get("code")
                        if code not in RETRY_API_ERRORS:
                            raise PlotSourceError(
                                f"API error {code!r} from {url}: "
                                f"{error.get('info', '')}"
                            )
                        problem = f"API error {code!r}"
                        retry_after = retry_after_seconds(response, 5)

            if attempt + 1 == self.max_tries:
                break
            retry_after = min(retry_after, MAX_RETRY_AFTER)
            logger.warning(f"{problem} from {url}, backing off {retry_after}s")
            self.sleep(retry_after)
        raise PlotSourceError(f"Gave up on {url} after {self.max_tries} tries.")


def retry_after_seconds(response, default):
    """Retry-After as seconds. It may be a number or an HTTP date."""
    value = response.headers.get("Retry-After")
    if value is None:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, when.timestamp() - time.time())


def make_client(contact=None, **kwargs):
    """Client with the User-Agent Wikimedia's API etiquette asks for."""
    contact = contact or os.environ.get("WIKIMEDIA_CONTACT")
    if not contact:
        raise PlotSourceError(
            "Set WIKIMEDIA_CONTACT to a contact address for the User-Agent."
        )
    session = requests.Session()
    session.headers["User-Agent"] = (
        f"MovieChooser/1.0 ({contact}) python-requests/{requests.__version__}"
    )
    return PoliteClient(session, **kwargs)


def article_url(title):
    # Keep the characters Wikipedia leaves bare in its own links; encode ?, # etc.
    path = quote(title.replace(" ", "_"), safe="/:(),'!*")
    return ENWIKI_ARTICLE_URL.format(title=path)


def _sparql_query(imdbids):
    values = " ".join(f'"{i}"' for i in imdbids)
    return f"""
SELECT ?imdb ?item ?title ?isFilm WHERE {{
  VALUES ?imdb {{ {values} }}
  ?item wdt:P345 ?imdb .
  ?article schema:about ?item ;
           schema:isPartOf <https://en.wikipedia.org/> ;
           schema:name ?title .
  BIND(EXISTS {{ ?item wdt:P31/wdt:P279* wd:Q11424 }} AS ?isFilm)
}}"""


def imdb_to_titles(client, imdbids, batch_size=SPARQL_BATCH_SIZE):
    """Map IMDb IDs to enwiki article titles. IDs with no article are left out.

    IDs that aren't "tt" plus digits are left out too: one bad ID would break
    the SPARQL query for its whole batch.
    """
    bad = [i for i in imdbids if not IMDB_ID.fullmatch(i)]
    if bad:
        logger.warning(f"Skipping malformed IMDb IDs: {bad}")
        imdbids = [i for i in imdbids if IMDB_ID.fullmatch(i)]
    candidates = {}
    for start in range(0, len(imdbids), batch_size):
        data = client.request_json(
            "POST",
            WIKIDATA_SPARQL_URL,
            data={"query": _sparql_query(imdbids[start : start + batch_size])},
            headers={"Accept": "application/sparql-results+json"},
        )
        for row in data["results"]["bindings"]:
            candidates.setdefault(row["imdb"]["value"], set()).add(
                (row["title"]["value"], row["isFilm"]["value"] == "true")
            )

    titles = {}
    for imdbid, options in candidates.items():
        # Prefer an item that is a film, then the shortest title.
        title, _ = min(options, key=lambda o: (not o[1], len(o[0]), o[0]))
        if len(options) > 1:
            logger.warning(f"{imdbid} matches {sorted(options)}, using {title!r}")
        titles[imdbid] = title
    return titles


def _wiki_query(client, **params):
    params.update(action="query", format="json", formatversion=2, maxlag=5)
    return client.request_json("GET", ENWIKI_API_URL, params=params)


def latest_revisions(client, titles, per_request=TITLES_PER_REQUEST):
    """Map each title to (resolved title, lastrevid). Missing pages are left out."""
    titles = list(dict.fromkeys(titles))
    revisions = {}
    for start in range(0, len(titles), per_request):
        batch = titles[start : start + per_request]
        query = _wiki_query(client, prop="info", redirects=1, titles="|".join(batch))[
            "query"
        ]
        renamed = {}
        for step in query.get("normalized", []) + query.get("redirects", []):
            renamed[step["from"]] = step["to"]
        pages = {p["title"]: p["lastrevid"] for p in query["pages"] if "lastrevid" in p}
        for title in batch:
            resolved, seen = title, {title}
            while resolved in renamed and renamed[resolved] not in seen:
                resolved = renamed[resolved]
                seen.add(resolved)
            if resolved in pages:
                revisions[title] = (resolved, pages[resolved])
    return revisions


def _has_pages(data):
    return isinstance(data, dict) and "pages" in data.get("query", {})


def _read_cache(path):
    """The cached response, or None if it is missing, truncated or not a result."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if _has_pages(data) else None


def fetch_extract(client, title, revid, cache_dir):
    """Plain text of the whole article, cached on disk by title and revision."""
    key = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
    path = Path(cache_dir) / f"{key}-{revid}.json"
    data = _read_cache(path)
    if data is None:
        data = _wiki_query(
            client,
            prop="extracts",
            explaintext=1,
            exsectionformat="wiki",
            redirects=1,
            titles=title,
        )
        if not _has_pages(data):
            raise PlotSourceError(f"No pages in the extract response for {title!r}")
        # Write then rename, so an interrupted run never leaves half a file.
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, path)
    pages = data["query"]["pages"]
    return pages[0].get("extract", "") if pages else ""


def _level2_heading(line):
    line = line.strip()
    if line.startswith("==") and not line.startswith("===") and line.endswith("=="):
        return line.strip("= ").lower()
    return None


def extract_plot_section(extract):
    """The first plot-like level-2 section, without subheadings, or None."""
    section = None
    for line in extract.splitlines():
        heading = _level2_heading(line)
        if heading is not None:
            if section is not None:
                break
            if heading in PLOT_HEADINGS:
                section = []
            continue
        if section is not None and not line.strip().startswith("=="):
            section.append(" ".join(line.split()))

    if section is None:
        return None
    text = "\n".join(p for p in section if p)
    return text if len(text.split()) >= MIN_PLOT_WORDS else None


def omdb_api_key():
    api_key = os.environ.get("OMDB_API_KEY")
    if not api_key:
        raise PlotSourceError("Set OMDB_API_KEY for the OMDb fallback.")
    return api_key


def fetch_omdb_plot(client, imdbid, api_key=None):
    """OMDb's full plot, or None when OMDb has none.

    OMDb answers Response "False" when the lookup fails, which is an error, not
    a missing plot: the caller would otherwise store the short plot as final.
    """
    data = client.request_json(
        "GET",
        OMDB_URL,
        params={"i": imdbid, "plot": "full", "apikey": api_key or omdb_api_key()},
    )
    if data.get("Response") != "True":
        raise PlotSourceError(f"OMDb error: {data.get('Error', 'no response')}")
    plot = (data.get("Plot") or "").strip()
    return plot if plot and plot != "N/A" else None
