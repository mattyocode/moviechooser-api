import pytest
import requests

from movies import plot_sources
from movies.plot_sources import PlotSourceError, PoliteClient


class FakeResponse:
    def __init__(self, data=None, status_code=200, headers=None):
        self.data = data or {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_client(*responses):
    sleeps = []
    client = PoliteClient(
        FakeSession(*responses), sleep=sleeps.append, clock=lambda: 0.0
    )
    return client, sleeps


def sparql_row(imdbid, title, is_film=True):
    return {
        "imdb": {"value": imdbid},
        "title": {"value": title},
        "isFilm": {"value": "true" if is_film else "false"},
    }


def sparql_response(*rows):
    return FakeResponse({"results": {"bindings": list(rows)}})


def words(n):
    return " ".join(["word"] * n)


# PoliteClient


def test_client_spaces_requests_out():
    client, sleeps = make_client(FakeResponse({"ok": 1}), FakeResponse({"ok": 2}))

    client.request_json("GET", "https://example.org")
    client.request_json("GET", "https://example.org")

    assert sleeps == [1.0]


def test_client_honours_retry_after_on_429_and_503():
    client, sleeps = make_client(
        FakeResponse(status_code=429, headers={"Retry-After": "7"}),
        FakeResponse(status_code=503),
        FakeResponse({"ok": True}),
    )

    assert client.request_json("GET", "https://example.org") == {"ok": True}
    assert 7.0 in sleeps
    assert 2.0 in sleeps  # no Retry-After on the second try: 2 ** 1


def test_client_backs_off_on_maxlag():
    client, sleeps = make_client(
        FakeResponse({"error": {"code": "maxlag"}}, headers={"Retry-After": "5"}),
        FakeResponse({"query": {}}),
    )

    assert client.request_json("GET", "https://example.org") == {"query": {}}
    assert 5.0 in sleeps


@pytest.mark.parametrize(
    "failure, backoff",
    [
        (FakeResponse(status_code=500), 1),
        (FakeResponse(status_code=504), 1),
        (FakeResponse({"error": {"code": "ratelimited"}}), 5),
        (requests.ConnectionError("refused"), 1),
        (requests.Timeout("slow"), 1),
    ],
)
def test_client_retries_transient_failures(failure, backoff):
    client, sleeps = make_client(failure, FakeResponse({"ok": True}))

    assert client.request_json("GET", "https://example.org") == {"ok": True}
    assert sleeps[0] == backoff


def test_client_raises_on_other_api_errors():
    client, _ = make_client(
        FakeResponse({"error": {"code": "badvalue", "info": "Bad prop."}})
    )

    with pytest.raises(PlotSourceError, match="badvalue"):
        client.request_json("GET", "https://example.org")


def test_client_errors_never_include_query_parameters():
    secret = "s3cret"
    leaky = requests.ConnectionError(
        f"Max retries exceeded with url: /?apikey={secret}"
    )
    client, _ = make_client(FakeResponse(status_code=401), *[leaky] * 5)

    for _ in range(2):
        with pytest.raises(PlotSourceError) as error:
            client.request_json("GET", "https://example.org", params={"apikey": secret})
        assert secret not in str(error.value)
        assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "header, expected",
    [
        ("7", 7.0),
        ("Wed, 21 Oct 2015 07:28:00 GMT", 0.0),  # in the past
        ("soon", 4),
    ],
)
def test_client_reads_retry_after_seconds_or_date(header, expected):
    response = FakeResponse(status_code=503, headers={"Retry-After": header})

    assert plot_sources.retry_after_seconds(response, 4) == expected


def test_client_gives_up_after_max_tries():
    client, _ = make_client(*[FakeResponse(status_code=429)] * 5)

    with pytest.raises(PlotSourceError):
        client.request_json("GET", "https://example.org")


def test_make_client_requires_contact(monkeypatch):
    monkeypatch.delenv("WIKIMEDIA_CONTACT", raising=False)

    with pytest.raises(PlotSourceError):
        plot_sources.make_client()


def test_make_client_sets_user_agent():
    client = plot_sources.make_client(contact="me@example.org")

    assert "(me@example.org)" in client.session.headers["User-Agent"]
    assert client.session.headers["User-Agent"].startswith("MovieChooser/1.0")


@pytest.mark.parametrize(
    "title, url",
    [
        ("Heat (1995 film)", "Heat_(1995_film)"),
        ("Dude, Where's My Car?", "Dude,_Where's_My_Car%3F"),
        ("100% Wolf", "100%25_Wolf"),
        ("Amélie", "Am%C3%A9lie"),
    ],
)
def test_article_url_encodes_title(title, url):
    assert plot_sources.article_url(title) == f"https://en.wikipedia.org/wiki/{url}"


# Wikidata


def test_imdb_to_titles_batches_and_skips_unmatched():
    client, _ = make_client(
        sparql_response(sparql_row("tt1", "One")),
        sparql_response(sparql_row("tt3", "Three")),
    )

    titles = plot_sources.imdb_to_titles(client, ["tt1", "tt2", "tt3"], batch_size=2)

    assert titles == {"tt1": "One", "tt3": "Three"}
    queries = [kwargs["data"]["query"] for _, _, kwargs in client.session.calls]
    assert '"tt1" "tt2"' in queries[0] and '"tt3"' in queries[1]


def test_imdb_to_titles_prefers_film_then_shortest_title():
    client, _ = make_client(
        sparql_response(
            sparql_row("tt1", "Heat", is_film=False),
            sparql_row("tt1", "Heat (1995 film) extended", is_film=True),
            sparql_row("tt1", "Heat (1995 film)", is_film=True),
        )
    )

    assert plot_sources.imdb_to_titles(client, ["tt1"]) == {"tt1": "Heat (1995 film)"}


# MediaWiki revisions


def test_latest_revisions_batches_50_titles_per_request():
    titles = [f"Film {i}" for i in range(51)]
    first = {"query": {"pages": [{"title": t, "lastrevid": 1} for t in titles[:50]]}}
    second = {"query": {"pages": [{"title": titles[50], "lastrevid": 2}]}}
    client, _ = make_client(FakeResponse(first), FakeResponse(second))

    revisions = plot_sources.latest_revisions(client, titles)

    assert len(client.session.calls) == 2
    assert client.session.calls[0][2]["params"]["titles"].count("|") == 49
    assert revisions["Film 50"] == ("Film 50", 2)


def test_latest_revisions_follows_redirects_and_skips_missing():
    data = {
        "query": {
            "redirects": [{"from": "Old Name", "to": "New Name"}],
            "pages": [
                {"title": "New Name", "lastrevid": 42},
                {"title": "Gone", "missing": True},
            ],
        }
    }
    client, _ = make_client(FakeResponse(data))

    revisions = plot_sources.latest_revisions(client, ["Old Name", "Gone"])

    assert revisions == {"Old Name": ("New Name", 42)}


def test_latest_revisions_stops_on_a_redirect_loop():
    data = {
        "query": {
            "redirects": [{"from": "A", "to": "B"}, {"from": "B", "to": "A"}],
            "pages": [],
        }
    }
    client, _ = make_client(FakeResponse(data))

    assert plot_sources.latest_revisions(client, ["A", "B"]) == {}


# Extracts and cache


def test_fetch_extract_uses_cache_on_second_call(tmp_path):
    data = {"query": {"pages": [{"title": "Film", "extract": "== Plot ==\nText"}]}}
    client, _ = make_client(FakeResponse(data))

    first = plot_sources.fetch_extract(client, "Film", 7, tmp_path)
    second = plot_sources.fetch_extract(client, "Film", 7, tmp_path)

    assert first == second == "== Plot ==\nText"
    assert len(client.session.calls) == 1


def test_fetch_extract_refetches_new_revision(tmp_path):
    data = {"query": {"pages": [{"title": "Film", "extract": "text"}]}}
    client, _ = make_client(FakeResponse(data), FakeResponse(data))

    plot_sources.fetch_extract(client, "Film", 7, tmp_path)
    plot_sources.fetch_extract(client, "Film", 8, tmp_path)

    assert len(client.session.calls) == 2


def test_fetch_extract_does_not_cache_a_response_without_pages(tmp_path):
    client, _ = make_client(FakeResponse({"batchcomplete": True}))

    with pytest.raises(PlotSourceError):
        plot_sources.fetch_extract(client, "Film", 7, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("cached", ['{"query": {"pa', '{"error": {"code": "x"}}'])
def test_fetch_extract_refetches_a_bad_cache_file(tmp_path, cached):
    data = {"query": {"pages": [{"title": "Film", "extract": "text"}]}}
    client, _ = make_client(FakeResponse(data))
    plot_sources.fetch_extract(client, "Film", 7, tmp_path)
    (path,) = tmp_path.iterdir()
    path.write_text(cached)
    client.session.responses.append(FakeResponse(data))

    assert plot_sources.fetch_extract(client, "Film", 7, tmp_path) == "text"
    assert len(client.session.calls) == 2
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


# Plot section


@pytest.mark.parametrize(
    "heading",
    [
        "Plot",
        "Plot summary",
        "Synopsis",
        "Premise",
        "Story",
        "Storylines",
        "Summary",
        "Overview",
        "Content",
        "Subject matter",
    ],
)
def test_extract_plot_section_accepts_plot_headings(heading):
    extract = f"Intro.\n\n== {heading} ==\n{words(40)}\n\n== Cast ==\nSomeone"

    assert plot_sources.extract_plot_section(extract) == words(40)


def test_extract_plot_section_drops_subheadings_and_keeps_paragraphs():
    extract = (
        "== Plot ==\n"
        f"{words(20)}\n\n"
        "=== Part two ===\n"
        f"{words(20)}   \n"
        "== Production ==\nBudget"
    )

    assert plot_sources.extract_plot_section(extract) == f"{words(20)}\n{words(20)}"


def test_extract_plot_section_none_without_match():
    extract = f"== Synopsis of production ==\n{words(40)}\n== Cast ==\nSomeone"

    assert plot_sources.extract_plot_section(extract) is None


def test_extract_plot_section_none_when_too_short():
    assert plot_sources.extract_plot_section(f"== Plot ==\n{words(29)}") is None


# OMDb


def test_fetch_omdb_plot_requests_full_plot():
    client, _ = make_client(FakeResponse({"Response": "True", "Plot": "Long plot."}))

    assert plot_sources.fetch_omdb_plot(client, "tt1", api_key="k") == "Long plot."
    assert client.session.calls[0][2]["params"]["plot"] == "full"


def test_fetch_omdb_plot_none_for_na():
    client, _ = make_client(FakeResponse({"Response": "True", "Plot": "N/A"}))

    assert plot_sources.fetch_omdb_plot(client, "tt1", api_key="k") is None


def test_fetch_omdb_plot_requires_api_key(monkeypatch):
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    client, _ = make_client()

    with pytest.raises(PlotSourceError, match="OMDB_API_KEY"):
        plot_sources.fetch_omdb_plot(client, "tt1")
