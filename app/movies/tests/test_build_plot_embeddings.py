from datetime import datetime, timezone
from io import StringIO

import numpy as np
import pytest
from django.core.management import call_command

from movies import embeddings
from movies.models import Genre, Movie, MoviePlot

from ..management.commands.build_plot_embeddings import PLOT, PREMISE, Command
from .factories import MoviePlotFactory

ORIGINAL_MODEL = embeddings.MODEL_NAME


def run(*args):
    out = StringIO()
    call_command("build_plot_embeddings", *args, stdout=out, stderr=StringIO())
    return out.getvalue().strip()


def summary(
    plot,
    plot_skipped,
    premise,
    premise_skipped,
    empty=0,
    cleared=0,
    plot_left=0,
    premise_left=0,
    plot_empty=0,
    plot_cleared=0,
    total=None,
    dry=False,
):
    verb, clear_verb = (
        ("would embed", "would clear") if dry else ("embedded", "cleared")
    )
    if total is None:
        total = plot + plot_skipped + plot_left + plot_empty
    return (
        f"plot: {verb} {plot}, skipped {plot_skipped}, left {plot_left}, "
        f"empty {plot_empty}, {clear_verb} {plot_cleared} | "
        f"premise: {verb} {premise}, skipped {premise_skipped}, "
        f"left {premise_left}, empty {empty}, {clear_verb} {cleared} | "
        f"total {total}"
    )


def make_plots(n):
    """MoviePlot rows whose movies have a short plot, so both passes run."""
    return [
        MoviePlotFactory(movie__plot=f"A driver plans heist number {i}.")
        for i in range(n)
    ]


def vectors(field):
    return {p.pk: getattr(p, field) for p in MoviePlot.objects.all()}


@pytest.mark.django_db
def test_first_run_embeds_both_vectors_then_second_run_none():
    make_plots(3)

    assert run() == summary(3, 0, 3, 0)
    for plot in MoviePlot.objects.select_related("movie"):
        assert plot.model_name == embeddings.MODEL_NAME
        assert plot.premise_model_name == embeddings.MODEL_NAME
        assert plot.embedded_text_hash == embeddings.text_hash(plot.text)
        assert plot.premise_text_hash == embeddings.text_hash(
            embeddings.premise_text(plot.movie)
        )
        assert np.isclose(np.linalg.norm(plot.embedding), 1.0)
        assert np.isclose(np.linalg.norm(plot.premise_embedding), 1.0)

    assert run() == summary(0, 3, 0, 3)


@pytest.mark.django_db
def test_changed_text_re_embeds_only_that_rows_plot_vector():
    changed, unchanged = make_plots(2)
    run()
    plot_before, premise_before = vectors("embedding"), vectors("premise_embedding")

    MoviePlot.objects.filter(pk=changed.pk).update(text="A different plot.")

    assert run() == summary(1, 1, 0, 2)
    changed.refresh_from_db()
    assert changed.embedded_text_hash == embeddings.text_hash("A different plot.")
    assert np.allclose(vectors("embedding")[unchanged.pk], plot_before[unchanged.pk])
    for pk, vector in vectors("premise_embedding").items():
        assert np.allclose(vector, premise_before[pk])


@pytest.mark.django_db
def test_changed_movie_plot_re_embeds_only_that_rows_premise():
    changed, unchanged = make_plots(2)
    run()
    plot_before, premise_before = vectors("embedding"), vectors("premise_embedding")

    Movie.objects.filter(pk=changed.pk).update(plot="A chef opens a restaurant.")

    assert run() == summary(0, 2, 1, 1)
    assert not np.allclose(
        vectors("premise_embedding")[changed.pk], premise_before[changed.pk]
    )
    assert np.allclose(
        vectors("premise_embedding")[unchanged.pk], premise_before[unchanged.pk]
    )
    for pk, vector in vectors("embedding").items():
        assert np.allclose(vector, plot_before[pk])


@pytest.mark.django_db
def test_changed_genres_re_embed_only_that_rows_premise():
    changed, _ = make_plots(2)
    run()

    changed.movie.genre.add(Genre.objects.create(name="Crime"))

    assert run() == summary(0, 2, 1, 1)
    changed.refresh_from_db()
    assert changed.premise_text_hash == embeddings.text_hash(
        "Crime. A driver plans heist number 0."
    )


@pytest.mark.django_db
def test_model_change_re_embeds_both_vectors_in_one_run(monkeypatch):
    make_plots(2)
    run()

    monkeypatch.setattr(embeddings, "MODEL_NAME", "other/model")

    assert run() == summary(2, 0, 2, 0)
    for field in ("model_name", "premise_model_name"):
        assert set(MoviePlot.objects.values_list(field, flat=True)) == {"other/model"}
    assert run() == summary(0, 2, 0, 2)


@pytest.mark.django_db
def test_limit_picking_different_rows_per_pass_leaves_nothing_stale(monkeypatch):
    # A is on the new model but its premise changed; B is still on the old one.
    # With --limit 1 the plot pass takes B and the premise pass takes A.
    a, b = (
        MoviePlotFactory(movie__imdbid=imdbid, movie__plot="A driver plans a heist.")
        for imdbid in ("tt0000001", "tt0000002")
    )
    run()
    monkeypatch.setattr(embeddings, "MODEL_NAME", "other/model")
    run("--imdbid", a.pk)
    Movie.objects.filter(pk=a.pk).update(plot="A chef opens a restaurant.")

    assert run("--limit", "1") == summary(1, 1, 1, 0, premise_left=1)
    b.refresh_from_db()
    assert b.model_name == "other/model"
    assert b.premise_model_name == ORIGINAL_MODEL

    assert run() == summary(0, 2, 1, 1)
    assert run() == summary(0, 2, 0, 2)
    for field in ("model_name", "premise_model_name"):
        assert set(MoviePlot.objects.values_list(field, flat=True)) == {"other/model"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "crashing_pass, expected",
    [
        # Premises run first, so the plot pass never started either.
        (PREMISE, (2, 0, 2, 0)),
        (PLOT, (2, 0, 0, 2)),
    ],
)
def test_interrupted_pass_is_finished_by_the_next_run(
    monkeypatch, crashing_pass, expected
):
    make_plots(2)
    run()
    monkeypatch.setattr(embeddings, "MODEL_NAME", "other/model")

    embed = Command.embed

    def crash(self, vector, *args, **kwargs):
        if vector == crashing_pass:
            raise RuntimeError("interrupted")
        return embed(self, vector, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(Command, "embed", crash)
        with pytest.raises(RuntimeError):
            run()

    assert run() == summary(*expected)
    for field in ("model_name", "premise_model_name"):
        assert set(MoviePlot.objects.values_list(field, flat=True)) == {"other/model"}


@pytest.mark.django_db
def test_movie_without_genres_or_plot_is_empty():
    make_plots(1)
    blank = MoviePlotFactory(movie__plot="  ")

    assert run() == summary(2, 0, 1, 0, empty=1)
    blank.refresh_from_db()
    assert blank.premise_embedding is None
    assert blank.premise_text_hash == ""


@pytest.mark.django_db
def test_premise_vector_is_cleared_when_premise_becomes_empty():
    (plot,) = make_plots(1)
    run()

    Movie.objects.filter(pk=plot.pk).update(plot=None)

    assert run("--dry-run") == summary(0, 1, 0, 0, empty=1, cleared=1, dry=True)
    assert run() == summary(0, 1, 0, 0, empty=1, cleared=1)
    plot.refresh_from_db()
    assert plot.premise_embedding is None
    assert plot.premise_model_name == ""
    assert plot.premise_text_hash == ""
    assert run() == summary(0, 1, 0, 0, empty=1)


@pytest.mark.django_db
def test_plot_vector_is_cleared_when_plot_text_becomes_empty():
    (plot,) = make_plots(1)
    run()

    MoviePlot.objects.filter(pk=plot.pk).update(text="")

    assert run("--dry-run") == summary(
        0, 0, 0, 1, plot_empty=1, plot_cleared=1, dry=True
    )
    assert run() == summary(0, 0, 0, 1, plot_empty=1, plot_cleared=1)
    plot.refresh_from_db()
    assert plot.embedding is None
    assert plot.model_name == ""
    assert plot.embedded_text_hash == ""
    assert plot.premise_embedding is not None
    assert run() == summary(0, 0, 0, 1, plot_empty=1)


@pytest.mark.django_db
def test_limit_covers_embeds_and_clears_together():
    plots = make_plots(3)
    run()
    MoviePlot.objects.filter(pk=plots[0].pk).update(text="A new plot.")
    MoviePlot.objects.filter(pk__in=[p.pk for p in plots[1:]]).update(text="")

    assert run("--limit", "2") == summary(
        1, 0, 0, 3, plot_empty=2, plot_cleared=1, plot_left=1, total=3
    )
    assert run() == summary(0, 1, 0, 3, plot_empty=2, plot_cleared=1)


@pytest.mark.django_db
def test_dry_run_writes_nothing():
    make_plots(2)

    assert run("--dry-run") == summary(2, 0, 2, 0, dry=True)
    assert not MoviePlot.objects.filter(embedding__isnull=False).exists()
    assert not MoviePlot.objects.filter(premise_embedding__isnull=False).exists()


@pytest.mark.django_db
def test_limit_imdbid_and_force():
    make_plots(2)

    assert run("--limit", "1") == summary(1, 0, 1, 0, plot_left=1, premise_left=1)
    remaining = MoviePlot.objects.get(embedding__isnull=True)
    assert run("--imdbid", remaining.pk) == summary(1, 0, 1, 0)
    assert run("--force", "--batch-size", "1") == summary(2, 0, 2, 0)


@pytest.mark.django_db
def test_plot_row_without_text_is_counted_and_does_not_block_others():
    # Sorted first, so it would otherwise fail the batch the good row is in.
    bad = MoviePlotFactory(
        movie__imdbid="tt0000001", movie__plot="A thief plans one last job.", text=" "
    )
    good = MoviePlotFactory(movie__imdbid="tt0000002", movie__plot="A heist.")

    assert run() == summary(1, 0, 2, 0, plot_empty=1)
    bad.refresh_from_db()
    good.refresh_from_db()
    assert bad.embedding is None
    assert bad.premise_model_name == embeddings.MODEL_NAME
    assert good.embedding is not None
    assert run() == summary(0, 1, 0, 2, plot_empty=1)


@pytest.mark.django_db
def test_limit_reports_stale_rows_it_left():
    make_plots(3)

    assert run("--limit", "1", "--dry-run") == summary(
        1, 0, 1, 0, plot_left=2, premise_left=2, dry=True
    )
    run("--limit", "1")
    assert run("--limit", "1") == summary(1, 1, 1, 1, plot_left=1, premise_left=1)
    assert run() == summary(1, 2, 1, 2)


@pytest.mark.django_db
def test_embedding_and_clearing_update_updated_at():
    keep, cleared = make_plots(2)
    run()
    MoviePlot.objects.update(updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc))

    Movie.objects.filter(pk=keep.pk).update(plot="A chef opens a restaurant.")
    Movie.objects.filter(pk=cleared.pk).update(plot=None)
    run()

    for plot in (keep, cleared):
        plot.refresh_from_db()
        assert plot.updated_at.year > 2020
