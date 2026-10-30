from io import StringIO

import numpy as np
import pytest
from django.core.management import call_command

from movies import embeddings
from movies.models import MoviePlot

from .factories import MoviePlotFactory


def run(*args):
    out = StringIO()
    call_command("build_plot_embeddings", *args, stdout=out, stderr=StringIO())
    return out.getvalue().strip()


@pytest.mark.django_db
def test_first_run_embeds_every_row_then_second_run_none():
    MoviePlotFactory.create_batch(3)

    assert run() == "embedded 3 | skipped 0 | total 3"
    for plot in MoviePlot.objects.all():
        assert plot.model_name == embeddings.MODEL_NAME
        assert plot.embedded_text_hash == embeddings.text_hash(plot.text)
        assert np.isclose(np.linalg.norm(plot.embedding), 1.0)

    assert run() == "embedded 0 | skipped 3 | total 3"


@pytest.mark.django_db
def test_changed_text_re_embeds_only_that_row():
    changed, unchanged = MoviePlotFactory.create_batch(2)
    run()
    unchanged_before = MoviePlot.objects.get(pk=unchanged.pk).embedding

    MoviePlot.objects.filter(pk=changed.pk).update(text="A different plot.")

    assert run() == "embedded 1 | skipped 1 | total 2"
    changed.refresh_from_db()
    assert changed.embedded_text_hash == embeddings.text_hash("A different plot.")
    assert np.allclose(
        MoviePlot.objects.get(pk=unchanged.pk).embedding, unchanged_before
    )


@pytest.mark.django_db
def test_model_change_re_embeds_every_row(monkeypatch):
    MoviePlotFactory.create_batch(2)
    run()

    monkeypatch.setattr(embeddings, "MODEL_NAME", "other/model")

    assert run() == "embedded 2 | skipped 0 | total 2"
    assert set(MoviePlot.objects.values_list("model_name", flat=True)) == {
        "other/model"
    }


@pytest.mark.django_db
def test_dry_run_writes_nothing():
    MoviePlotFactory.create_batch(2)

    assert run("--dry-run") == "would embed 2 | skipped 0 | total 2"
    assert not MoviePlot.objects.filter(embedding__isnull=False).exists()


@pytest.mark.django_db
def test_limit_imdbid_and_force():
    MoviePlotFactory.create_batch(2)

    assert run("--limit", "1") == "embedded 1 | skipped 1 | total 2"
    remaining = MoviePlot.objects.get(embedding__isnull=True)
    assert run("--imdbid", remaining.pk) == "embedded 1 | skipped 0 | total 1"
    assert run("--force", "--batch-size", "1") == "embedded 2 | skipped 0 | total 2"
