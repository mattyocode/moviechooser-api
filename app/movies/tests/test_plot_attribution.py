import pytest

from movies import embeddings
from movies.models import MoviePlot, PlotSource

from .factories import MovieFactory, MoviePlotFactory
from .test_similar import vec

BABY_DRIVER = "https://en.wikipedia.org/wiki/Baby_Driver"


@pytest.fixture(autouse=True)
def query_vector(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_query", lambda text: vec(1))


def with_plot(slug, source=PlotSource.WIKIPEDIA, url=BABY_DRIVER, revid=1382739974):
    movie = MovieFactory.create(slug=slug, title=slug.title(), review=[80])
    plot = MoviePlotFactory.create(
        movie=movie,
        source=source,
        source_url=url,
        source_revid=revid,
        text="Secret plot text.",
        embedding=vec(1),
        premise_embedding=vec(1),
    )
    MoviePlot.objects.filter(pk=plot.pk).update(
        model_name=embeddings.MODEL_NAME, premise_model_name=embeddings.MODEL_NAME
    )
    return movie


def by_slug(items):
    return {item["slug"]: item for item in items}


@pytest.mark.django_db
def test_wikipedia_plot_links_the_stored_revision(client):
    with_plot("baby-driver")

    resp = client.get("/api/movies/baby-driver/")

    assert resp.data["plot_source_url"] == f"{BABY_DRIVER}?oldid=1382739974"


@pytest.mark.django_db
def test_wikipedia_plot_without_revid_links_the_article(client):
    with_plot("baby-driver", revid=None)

    resp = client.get("/api/movies/baby-driver/")

    assert resp.data["plot_source_url"] == BABY_DRIVER


@pytest.mark.django_db
def test_omdb_plot_has_no_source_url(client):
    with_plot(
        "omdb-movie",
        source=PlotSource.OMDB,
        url="https://www.imdb.com/title/tt0032455/",
        revid=None,
    )

    resp = client.get("/api/movies/omdb-movie/")

    assert resp.data["plot_source_url"] is None


@pytest.mark.django_db
def test_movie_without_plot_has_no_source_url(client):
    MovieFactory.create(slug="no-plot", review=[80])

    resp = client.get("/api/movies/no-plot/")

    assert resp.data["plot_source_url"] is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url, results",
    [
        ("/api/movies/", lambda data: data["results"]),
        ("/api/movies/?q=heist", lambda data: data["results"]),
        ("/api/movies/baby-driver/similar/", lambda data: data),
    ],
)
def test_lists_carry_source_url_but_never_plot_text(client, url, results):
    with_plot("baby-driver")
    with_plot("other", url="https://en.wikipedia.org/wiki/Other", revid=7)

    resp = client.get(url)

    items = by_slug(results(resp.data))
    assert items["other"]["plot_source_url"] == (
        "https://en.wikipedia.org/wiki/Other?oldid=7"
    )
    assert "Secret plot text." not in resp.content.decode()


@pytest.mark.django_db
def test_random_movie_carries_source_url(client):
    with_plot("baby-driver")

    resp = client.get("/api/movies/random/")

    assert resp.data["plot_source_url"] == f"{BABY_DRIVER}?oldid=1382739974"
