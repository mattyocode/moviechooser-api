"""Plot text from English Wikipedia (via Wikidata's IMDb ID property) and OMDb."""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

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
        for attempt in range(self.max_tries):
            if self._last is not None:
                wait = self.min_interval - (self.clock() - self._last)
                if wait > 0:
                    self.sleep(wait)
            response = self.session.request(method, url, timeout=60, **kwargs)
            self._last = self.clock()

            if response.status_code in (429, 503):
                retry_after = response.headers.get("Retry-After", 2**attempt)
            else:
                response.raise_for_status()
                data = response.json()
                error = data.get("error") if isinstance(data, dict) else None
                if not error or error.get("code") != "maxlag":
                    return data
                retry_after = response.headers.get("Retry-After", 5)

            logger.warning(f"Backing off {retry_after}s from {url}")
            self.sleep(float(retry_after))
        raise PlotSourceError(f"Gave up on {url} after {self.max_tries} tries.")


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
    return ENWIKI_ARTICLE_URL.format(title=title.replace(" ", "_"))


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
    """Map IMDb IDs to enwiki article titles. IDs with no article are left out."""
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
            resolved = title
            while resolved in renamed:
                resolved = renamed[resolved]
            if resolved in pages:
                revisions[title] = (resolved, pages[resolved])
    return revisions


def fetch_extract(client, title, revid, cache_dir):
    """Plain text of the whole article, cached on disk by title and revision."""
    key = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
    path = Path(cache_dir) / f"{key}-{revid}.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = _wiki_query(
            client,
            prop="extracts",
            explaintext=1,
            exsectionformat="wiki",
            redirects=1,
            titles=title,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
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


def fetch_omdb_plot(client, imdbid, api_key=None):
    """OMDb's full plot, or None."""
    api_key = api_key or os.environ.get("OMDB_API_KEY")
    if not api_key:
        return None
    data = client.request_json(
        "GET", OMDB_URL, params={"i": imdbid, "plot": "full", "apikey": api_key}
    )
    plot = data.get("Plot")
    if data.get("Response") == "True" and plot and plot != "N/A":
        return plot
    return None
