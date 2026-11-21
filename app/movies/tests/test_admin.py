import numpy as np
import pytest
from django.contrib.admin.sites import site

from movies.models import MoviePlot

from .factories import MovieFactory, MoviePlotFactory


@pytest.fixture
def plots():
    with_premise = MoviePlotFactory(
        premise_embedding=np.ones(384, dtype=np.float32),
        premise_model_name="old/model",
    )
    return with_premise, MoviePlotFactory()


@pytest.mark.django_db
def test_movieplot_changelist_shows_premise_flag_and_filters_by_premise_model(
    admin_client, plots
):
    url = "/admin/movies/movieplot/"

    resp = admin_client.get(url)
    assert resp.status_code == 200
    flags = {p.pk: p.has_premise for p in resp.context["cl"].result_list}
    assert flags == {plots[0].pk: True, plots[1].pk: False}

    resp = admin_client.get(url, {"premise_model_name": "old/model"})
    assert [p.pk for p in resp.context["cl"].result_list] == [plots[0].pk]


@pytest.mark.django_db
def test_movieplot_changelist_does_not_load_vectors_or_text(rf, plots):
    queryset = site._registry[MoviePlot].get_queryset(rf.get("/"))

    assert {
        "text",
        "embedding",
        "premise_embedding",
    } <= queryset.first().get_deferred_fields()


@pytest.mark.django_db
def test_movie_tmdb_id_can_be_corrected_in_admin(admin_client):
    movie = MovieFactory(tmdb_id=111, plot="A heist.", language="English", country="US")
    url = f"/admin/movies/movie/{movie.pk}/change/"

    form = admin_client.get(url).context["adminform"].form
    assert "tmdb_id" in form.fields

    data = {
        name: value
        for name, value in form.initial.items()
        if name in form.fields and value is not None
    }
    data["tmdb_id"] = 949
    resp = admin_client.post(url, data)
    assert resp.status_code == 302, resp.context["adminform"].form.errors
    movie.refresh_from_db()
    assert movie.tmdb_id == 949


@pytest.mark.django_db
def test_movie_poster_path_can_be_edited_in_admin(admin_client):
    movie = MovieFactory(
        poster_path="/real.jpg", plot="A heist.", language="English", country="US"
    )
    url = f"/admin/movies/movie/{movie.pk}/change/"

    form = admin_client.get(url).context["adminform"].form
    assert "poster_path" in form.fields

    data = {
        name: value
        for name, value in form.initial.items()
        if name in form.fields and value is not None
    }
    data["poster_path"] = "/deliberately-broken.jpg"
    resp = admin_client.post(url, data)
    assert resp.status_code == 302, resp.context["adminform"].form.errors
    movie.refresh_from_db()
    assert movie.poster_path == "/deliberately-broken.jpg"


@pytest.mark.django_db
def test_movie_changelist_shows_poster_path(admin_client):
    MovieFactory(poster_path="/listed.jpg")

    resp = admin_client.get("/admin/movies/movie/")

    assert resp.status_code == 200
    assert "/listed.jpg" in resp.content.decode()
