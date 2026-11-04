import numpy as np
import pytest

from accounts.models import CustomUser
from lists.models import Item, List
from movies import embeddings

from .factories import MovieFactory, MoviePlotFactory

DEFAULT_LIST = "watch-list"


def vec(*head):
    """A unit vector whose first components are head, padded with zeros."""
    vector = np.zeros(embeddings.DIMENSIONS, dtype=np.float32)
    vector[: len(head)] = head
    return vector / np.linalg.norm(vector)


def similar_url(slug, query=""):
    return f"/api/movies/{slug}/similar/{query}"


def slugs(resp):
    return [movie["slug"] for movie in resp.data]


@pytest.fixture
def movie_with_vectors():
    def _movie_with_vectors(slug, plot, premise, review=None, **kwargs):
        movie = MovieFactory.create(
            slug=slug, title=slug.title(), review=review or [80], **kwargs
        )
        MoviePlotFactory.create(movie=movie, embedding=plot, premise_embedding=premise)
        return movie

    return _movie_with_vectors


@pytest.fixture
def target(movie_with_vectors):
    return movie_with_vectors("target", vec(1), vec(1))


@pytest.fixture
def many_candidates(target, movie_with_vectors):
    """13 qualifying movies, nearest first: one more than the maximum limit."""
    return [
        movie_with_vectors(f"near-{i:02d}", vec(1, i * 0.1), vec(1, i * 0.1))
        for i in range(1, 14)
    ]


@pytest.mark.django_db
def test_similar_returns_plain_array(client, target, movie_with_vectors):
    movie_with_vectors("other", vec(1, 0.5), vec(1, 0.5))

    resp = client.get(similar_url("target"))

    assert resp.status_code == 200
    assert isinstance(resp.data, list)
    assert slugs(resp) == ["other"]


@pytest.mark.django_db
def test_similar_unknown_slug_is_404(client):
    resp = client.get(similar_url("no-such-movie"))

    assert resp.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_similar_rejects_writes(client, target, method):
    resp = getattr(client, method)(similar_url("target"))

    assert resp.status_code == 405


@pytest.mark.django_db
def test_similar_orders_closest_first(client, target, movie_with_vectors):
    movie_with_vectors("far", vec(1, 1), vec(1, 1))
    movie_with_vectors("near", vec(1, 0.1), vec(1, 0.1))

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["near", "far"]
    assert resp.data[0]["similarity"] > resp.data[1]["similarity"]


@pytest.mark.django_db
def test_similar_weighs_plot_and_premise_equally(client, target, movie_with_vectors):
    # Plot alone would put plot-twin first (distance 0 vs 0.2).
    movie_with_vectors("plot-twin", vec(1), vec(0, 1))
    movie_with_vectors("all-rounder", vec(0.8, 0.6), vec(0.8, 0.6))

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["all-rounder", "plot-twin"]
    assert resp.data[0]["similarity"] == pytest.approx(0.8, abs=1e-4)
    assert resp.data[1]["similarity"] == pytest.approx(0.5, abs=1e-4)


@pytest.mark.django_db
def test_similar_items_have_movie_fields_and_similarity(
    client, target, movie_with_vectors
):
    movie_with_vectors("other", vec(1, 0.5), vec(1, 0.5))

    resp = client.get(similar_url("target"))

    item = resp.data[0]
    for field in ("slug", "title", "poster_url", "genre", "avg_rating", "on_list"):
        assert field in item
    assert isinstance(item["similarity"], float)


@pytest.mark.django_db
def test_similar_on_list_for_signed_in_user(
    auth_user_client, target, movie_with_vectors
):
    user = CustomUser.objects.get(email="fixture@user.com")
    saved = movie_with_vectors("saved", vec(1, 0.1), vec(1, 0.1))
    movie_with_vectors("unsaved", vec(1, 1), vec(1, 1))
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(_list=_list, movie=saved)

    resp = auth_user_client.get(similar_url("target"))

    assert slugs(resp) == ["saved", "unsaved"]
    assert resp.data[0]["on_list"] is True
    assert resp.data[1]["on_list"] is False


@pytest.mark.django_db
def test_similar_on_list_false_for_anonymous_client(client, target, movie_with_vectors):
    user = CustomUser.objects.create(email="standard@user.com", password="test1234")
    saved = movie_with_vectors("saved", vec(1, 0.1), vec(1, 0.1))
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(_list=_list, movie=saved)

    resp = client.get(similar_url("target"))

    assert resp.status_code == 200
    assert resp.data[0]["on_list"] is False


@pytest.mark.django_db
def test_similar_excludes_requested_movie(client, target, movie_with_vectors):
    movie_with_vectors("twin", vec(1), vec(1))

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["twin"]


@pytest.mark.django_db
def test_similar_applies_rating_bar(client, target, movie_with_vectors):
    movie_with_vectors("rated-39", vec(1, 0.1), vec(1, 0.1), review=[39])
    movie_with_vectors("rated-40", vec(1, 0.2), vec(1, 0.2), review=[40])
    movie_with_vectors("unrated", vec(1, 0.3), vec(1, 0.3), review=[-1])

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["rated-40"]


@pytest.mark.django_db
def test_similar_excludes_movies_without_poster(client, target, movie_with_vectors):
    movie_with_vectors("no-poster", vec(1, 0.1), vec(1, 0.1), poster_url="N/A")
    movie_with_vectors("poster", vec(1, 0.2), vec(1, 0.2))

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["poster"]


@pytest.mark.django_db
def test_similar_empty_when_movie_has_no_plot_data(client, movie_with_vectors):
    MovieFactory.create(slug="bare")
    movie_with_vectors("other", vec(1), vec(1))

    resp = client.get(similar_url("bare"))

    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "plot, premise", [(vec(1), None), (None, vec(1))], ids=["no-premise", "no-plot"]
)
def test_similar_empty_when_movie_missing_a_vector(
    client, movie_with_vectors, plot, premise
):
    movie_with_vectors("half", plot, premise)
    movie_with_vectors("other", vec(1), vec(1))

    resp = client.get(similar_url("half"))

    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_similar_excludes_candidates_missing_a_vector(
    client, target, movie_with_vectors
):
    movie_with_vectors("no-premise", vec(1), None)
    movie_with_vectors("no-plot", None, vec(1))
    movie_with_vectors("whole", vec(1, 1), vec(1, 1))

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["whole"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query, expected",
    [
        ("", 6),
        ("?limit=3", 3),
        ("?limit=50", 12),
        ("?limit=0", 1),
        ("?limit=-5", 1),
        ("?limit=abc", 6),
    ],
)
def test_similar_limit(client, many_candidates, query, expected):
    resp = client.get(similar_url("target", query))

    assert resp.status_code == 200
    assert slugs(resp) == [movie.slug for movie in many_candidates[:expected]]


@pytest.mark.django_db
def test_similar_returns_fewer_than_limit(client, target, movie_with_vectors):
    movie_with_vectors("one", vec(1, 0.1), vec(1, 0.1))
    movie_with_vectors("two", vec(1, 0.2), vec(1, 0.2))

    resp = client.get(similar_url("target"))

    assert slugs(resp) == ["one", "two"]
