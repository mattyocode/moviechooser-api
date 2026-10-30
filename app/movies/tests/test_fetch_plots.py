from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from movies import plot_sources
from movies.models import MoviePlot, PlotSource

from .factories import MovieFactory, MoviePlotFactory

PLOT = " ".join(["Heroes"] * 40)


class FakeWeb:
    """What Wikidata, Wikipedia and OMDb return, keyed by IMDb ID or title."""

    def __init__(self, monkeypatch):
        self.titles, self.revisions, self.extracts, self.omdb = {}, {}, {}, {}
        self.extract_requests = []
        monkeypatch.setattr(plot_sources, "make_client", lambda: object())
        monkeypatch.setattr(
            plot_sources,
            "imdb_to_titles",
            lambda client, ids: {i: self.titles[i] for i in ids if i in self.titles},
        )
        monkeypatch.setattr(
            plot_sources,
            "latest_revisions",
            lambda client, titles: {
                t: (t, self.revisions[t]) for t in titles if t in self.revisions
            },
        )
        monkeypatch.setattr(plot_sources, "fetch_extract", self.fetch_extract)
        monkeypatch.setattr(
            plot_sources, "fetch_omdb_plot", lambda client, i: self.omdb.get(i)
        )

    def fetch_extract(self, client, title, revid, cache_dir):
        self.extract_requests.append(title)
        return self.extracts[title]

    def article(self, movie, title, revid, plot=PLOT):
        self.titles[movie.imdbid] = title
        self.revisions[title] = revid
        self.extracts[title] = f"Intro.\n== Plot ==\n{plot}\n== Cast ==\nSomeone"


@pytest.fixture
def web(monkeypatch):
    return FakeWeb(monkeypatch)


def run(*args):
    out = StringIO()
    call_command("fetch_plots", *args, stdout=out, stderr=StringIO())
    return out.getvalue().strip().splitlines()


@pytest.mark.django_db
def test_movie_with_article_gets_wikipedia_plot(web):
    movie = MovieFactory()
    web.article(movie, "Heat (1995 film)", 100)

    lines = run()

    plot = MoviePlot.objects.get(pk=movie.pk)
    assert plot.source == PlotSource.WIKIPEDIA
    assert plot.text == PLOT
    assert plot.source_url == "https://en.wikipedia.org/wiki/Heat_(1995_film)"
    assert plot.source_revid == 100
    assert lines[-1] == "movies 1 | wikipedia 1 | omdb 0 | missing 0 | unchanged 0"


@pytest.mark.django_db
def test_movie_without_article_falls_back_to_omdb(web):
    movie = MovieFactory()
    web.omdb[movie.imdbid] = "A long OMDb plot."

    lines = run()

    plot = MoviePlot.objects.get(pk=movie.pk)
    assert plot.source == PlotSource.OMDB
    assert plot.text == "A long OMDb plot."
    assert plot.source_url == f"https://www.imdb.com/title/{movie.imdbid}/"
    assert plot.source_revid is None
    assert lines[0] == f"no article (1): {movie.imdbid}"
    assert lines[-1].startswith("movies 1 | wikipedia 0 | omdb 1 | missing 0")


@pytest.mark.django_db
def test_article_without_plot_section_falls_back_to_short_plot(web):
    movie = MovieFactory(plot="Short stored plot.")
    web.article(movie, "Documentary", 5)
    web.extracts["Documentary"] = "== Production ==\nFilmed somewhere."

    lines = run()

    plot = MoviePlot.objects.get(pk=movie.pk)
    assert plot.source == PlotSource.OMDB
    assert plot.text == "Short stored plot."
    assert lines[0] == f"no plot section (1): {movie.imdbid}"


@pytest.mark.django_db
def test_unchanged_revision_is_skipped_without_extract_request(web):
    movie = MovieFactory()
    web.article(movie, "Heat", 100)
    run()
    web.extract_requests.clear()

    lines = run()

    assert web.extract_requests == []
    assert lines[-1].endswith("unchanged 1")


@pytest.mark.django_db
def test_changed_revision_updates_text_and_keeps_embedding(web):
    movie = MovieFactory()
    web.article(movie, "Heat", 100)
    run()
    MoviePlot.objects.filter(pk=movie.pk).update(embedding=[0.1] * 384)

    new_plot = " ".join(["Villains"] * 40)
    web.article(movie, "Heat", 101, plot=new_plot)
    run()

    plot = MoviePlot.objects.get(pk=movie.pk)
    assert plot.text == new_plot
    assert plot.source_revid == 101
    assert plot.embedding is not None


@pytest.mark.django_db
def test_existing_omdb_row_is_not_refetched_but_upgrades_to_wikipedia(web):
    plot = MoviePlotFactory(source=PlotSource.OMDB, source_revid=None, text="Old.")
    web.omdb[plot.pk] = "New OMDb text."

    run()
    assert MoviePlot.objects.get(pk=plot.pk).text == "Old."

    web.article(plot.movie, "Now Has Article", 9)
    run()
    assert MoviePlot.objects.get(pk=plot.pk).source == PlotSource.WIKIPEDIA


@pytest.mark.django_db
def test_dry_run_writes_nothing(web):
    movie = MovieFactory()
    web.article(movie, "Heat", 100)

    lines = run("--dry-run")

    assert not MoviePlot.objects.exists()
    assert lines[-1].startswith("dry run, nothing written | movies 1")


@pytest.mark.django_db
def test_requires_wikimedia_contact(monkeypatch):
    monkeypatch.delenv("WIKIMEDIA_CONTACT", raising=False)

    with pytest.raises(CommandError, match="WIKIMEDIA_CONTACT"):
        run()
