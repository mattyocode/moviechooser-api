import numpy as np
import pytest
from django.contrib.admin.sites import site

from movies.models import MoviePlot

from .factories import MoviePlotFactory


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
