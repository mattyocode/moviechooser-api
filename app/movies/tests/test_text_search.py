import datetime

import pytest
from django.conf import settings

from accounts.models import CustomUser
from lists.models import Item, List
from movies import embeddings, views
from movies.models import Genre, MoviePlot

from .factories import MoviePlotFactory, MovieWithGenreFactory
from .test_similar import vec

LIST_URL = "/api/movies/"
DEFAULT_LIST = "watch-list"


def slugs(resp):
    return [movie["slug"] for movie in resp.data["results"]]


def genre_id(name):
    return Genre.objects.get(name=name).id


@pytest.fixture(autouse=True)
def query_vector(monkeypatch):
    """Every query embeds to vec(1); tests record what text was embedded."""
    calls = []

    def fake_embed_query(text):
        calls.append(text)
        return vec(1)

    monkeypatch.setattr(embeddings, "embed_query", fake_embed_query)
    return calls


@pytest.fixture
def searchable():
    """A movie with plot and premise vectors from the current model."""

    def _searchable(slug, plot=None, premise=None, genre=None, **kwargs):
        kwargs.setdefault("review", [80])
        movie = MovieWithGenreFactory.create(
            slug=slug, title=slug.title(), genre=genre or ["Drama"], **kwargs
        )
        plot_data = MoviePlotFactory.create(
            movie=movie,
            embedding=vec(1) if plot is None else plot,
            premise_embedding=vec(1) if premise is None else premise,
        )
        MoviePlot.objects.filter(pk=plot_data.pk).update(
            model_name=embeddings.MODEL_NAME,
            premise_model_name=embeddings.MODEL_NAME,
        )
        return movie

    return _searchable


@pytest.fixture
def ranked(searchable):
    """n movies, nearest to the query first."""

    def _ranked(n, **kwargs):
        return [
            searchable(f"near-{i:02d}", vec(1, i * 0.05), vec(1, i * 0.05), **kwargs)
            for i in range(1, n + 1)
        ]

    return _ranked


def test_limits_fit_one_page():
    # Text results rely on fitting in page 1: see design D1.
    assert views.TEXT_SEARCH_LIMIT == 30
    assert views.TEXT_SEARCH_LIMIT <= settings.REST_FRAMEWORK["PAGE_SIZE"]
    assert views.TEXT_SEARCH_MAX_CHARS == 120


@pytest.mark.django_db
def test_text_query_returns_paginated_object(client, searchable):
    searchable("one")

    resp = client.get(LIST_URL, {"q": "i'm hungry"})

    assert resp.status_code == 200
    assert set(resp.data) == {"count", "next", "previous", "results"}
    assert slugs(resp) == ["one"]


@pytest.mark.django_db
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_query_matches_no_query(client, searchable, query_vector, blank):
    searchable("low", review=[50])
    searchable("high", review=[90])

    plain = client.get(LIST_URL)
    resp = client.get(LIST_URL, {"q": blank})

    assert resp.data == plain.data
    assert slugs(resp) == ["high", "low"]
    assert "similarity" not in resp.data["results"][0]
    assert query_vector == []


@pytest.mark.django_db
def test_orders_closest_first(client, searchable):
    searchable("far", vec(1, 1), vec(1, 1))
    searchable("near", vec(1, 0.1), vec(1, 0.1))

    resp = client.get(LIST_URL, {"q": "heist"})

    assert slugs(resp) == ["near", "far"]


@pytest.mark.django_db
def test_weighs_plot_and_premise_equally(client, searchable):
    # Plot alone would put plot-twin first (similarity 1 vs 0.8).
    searchable("plot-twin", vec(1), vec(0, 1))
    searchable("all-rounder", vec(0.8, 0.6), vec(0.8, 0.6))

    resp = client.get(LIST_URL, {"q": "heist"})

    assert slugs(resp) == ["all-rounder", "plot-twin"]
    assert resp.data["results"][0]["similarity"] == pytest.approx(0.8, abs=1e-4)
    assert resp.data["results"][1]["similarity"] == pytest.approx(0.5, abs=1e-4)


@pytest.mark.django_db
def test_ties_break_by_slug(client, searchable):
    searchable("bravo")
    searchable("alpha")

    resp = client.get(LIST_URL, {"q": "heist"})

    assert slugs(resp) == ["alpha", "bravo"]


@pytest.mark.django_db
def test_caps_results_at_30_in_one_page(client, ranked):
    ranked(35)

    resp = client.get(LIST_URL, {"q": "heist"})

    assert resp.data["count"] == 30
    assert len(resp.data["results"]) == 30
    assert resp.data["next"] is None
    assert slugs(resp) == [f"near-{i:02d}" for i in range(1, 31)]


@pytest.mark.django_db
def test_fewer_than_30_returns_them_all(client, ranked):
    ranked(12)

    resp = client.get(LIST_URL, {"q": "heist"})

    assert resp.data["count"] == 12
    assert slugs(resp) == [f"near-{i:02d}" for i in range(1, 13)]


@pytest.mark.django_db
def test_no_second_page(client, ranked):
    ranked(35)

    resp = client.get(LIST_URL, {"q": "heist", "page": 2})

    assert resp.status_code == 404


@pytest.mark.django_db
def test_genre_filter_applies_without_duplicates(client, searchable):
    searchable("both", genre=["Comedy", "Crime"])
    searchable("comedy", vec(1, 0.5), vec(1, 0.5), genre=["Comedy"])
    searchable("drama", genre=["Drama"])

    resp = client.get(
        LIST_URL,
        {"q": "heist", "g": f"{genre_id('Comedy')},{genre_id('Crime')}"},
    )

    assert slugs(resp) == ["both", "comedy"]
    assert resp.data["count"] == 2


@pytest.mark.django_db
def test_decade_and_runtime_filters_apply(client, searchable):
    nineties, eighties = datetime.date(1994, 6, 1), datetime.date(1985, 6, 1)
    searchable("fits", released=nineties, runtime=95)
    searchable("too-old", released=eighties, runtime=95)
    searchable("too-long", released=nineties, runtime=140)

    resp = client.get(
        LIST_URL, {"q": "heist", "dmin": "1990", "dmax": "1990", "rmax": "100"}
    )

    assert slugs(resp) == ["fits"]


@pytest.mark.django_db
def test_filters_excluding_everything_return_empty(client, searchable):
    searchable("drama", genre=["Drama"])
    comedy = Genre.objects.create(name="Comedy")

    resp = client.get(LIST_URL, {"q": "heist", "g": str(comedy.id)})

    assert resp.status_code == 200
    assert resp.data["count"] == 0
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_quality_bar_applies(client, searchable):
    searchable("poorly-reviewed", review=[30])
    searchable("no-poster", poster_url="N/A")
    searchable("fine", vec(1, 1), vec(1, 1))

    resp = client.get(LIST_URL, {"q": "heist"})

    assert slugs(resp) == ["fine"]


@pytest.mark.django_db
def test_movies_without_current_vectors_are_left_out(client, searchable):
    searchable("searchable")
    MovieWithGenreFactory.create(slug="no-plot-row", genre=["Drama"], review=[80])
    old = searchable("old-model")
    MoviePlot.objects.filter(movie=old).update(premise_model_name="old/model")

    resp = client.get(LIST_URL, {"q": "heist"})
    plain = client.get(LIST_URL)

    assert slugs(resp) == ["searchable"]
    assert set(slugs(plain)) == {"searchable", "no-plot-row", "old-model"}


@pytest.mark.django_db
def test_items_have_list_fields_and_similarity(client, searchable):
    searchable("near", vec(1, 0.1), vec(1, 0.1))
    searchable("far", vec(1, 1), vec(1, 1))

    resp = client.get(LIST_URL, {"q": "heist"})

    results = resp.data["results"]
    for field in ("slug", "title", "poster_url", "genre", "avg_rating", "on_list"):
        assert field in results[0]
    scores = [item["similarity"] for item in results]
    assert all(isinstance(score, float) for score in scores)
    assert scores == sorted(scores, reverse=True)


@pytest.mark.django_db
def test_on_list_for_signed_in_user(auth_user_client, searchable):
    user = CustomUser.objects.get(email="fixture@user.com")
    saved = searchable("saved", vec(1, 0.1), vec(1, 0.1))
    searchable("unsaved", vec(1, 1), vec(1, 1))
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(_list=_list, movie=saved)

    resp = auth_user_client.get(LIST_URL, {"q": "heist"})

    on_list = {item["slug"]: item["on_list"] for item in resp.data["results"]}
    assert on_list == {"saved": True, "unsaved": False}


@pytest.mark.django_db
def test_long_query_is_cut_to_120_characters(client, searchable, query_vector):
    searchable("one")
    long_query = "  " + "a" * 1000

    resp = client.get(LIST_URL, {"q": long_query})
    short = client.get(LIST_URL, {"q": "a" * 120})

    assert resp.status_code == 200
    assert query_vector == ["a" * 120, "a" * 120]
    assert resp.data == short.data


@pytest.mark.django_db
def test_unembeddable_query_is_503(client, searchable, monkeypatch):
    searchable("one")

    def broken(text):
        raise RuntimeError("model failed to load")

    monkeypatch.setattr(embeddings, "embed_query", broken)

    resp = client.get(LIST_URL, {"q": "heist"})
    plain = client.get(LIST_URL)

    assert resp.status_code == 503
    assert resp.data["detail"] == "Search is unavailable right now."
    assert plain.status_code == 200
