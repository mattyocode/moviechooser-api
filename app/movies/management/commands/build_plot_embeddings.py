from typing import NamedTuple

from django.core.management.base import BaseCommand
from django.utils import timezone

from movies import embeddings
from movies.models import MoviePlot


class Vector(NamedTuple):
    """The MoviePlot fields one embedding pass reads and writes."""

    label: str
    vector: str
    model_name: str
    text_hash: str

    @property
    def fields(self):
        return [self.vector, self.model_name, self.text_hash, "updated_at"]


PLOT = Vector("plot", "embedding", "model_name", "embedded_text_hash")
PREMISE = Vector(
    "premise", "premise_embedding", "premise_model_name", "premise_text_hash"
)


def is_stale(plot: MoviePlot, vector: Vector, current_hash: str) -> bool:
    return (
        getattr(plot, vector.vector) is None
        or getattr(plot, vector.model_name) != embeddings.MODEL_NAME
        or getattr(plot, vector.text_hash) != current_hash
    )


class Command(BaseCommand):
    help = (
        "Embed MoviePlot text and each movie's premise (genres plus OMDb short "
        "plot). Only vectors that are missing, from a different model or from "
        "changed text are embedded, so re-running is cheap."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Embed at most N rows per pass.")
        parser.add_argument(
            "--imdbid", action="append", help="Only this movie (repeatable)."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Count rows, write nothing."
        )
        parser.add_argument(
            "--force", action="store_true", help="Re-embed every selected row."
        )
        parser.add_argument("--batch-size", type=int, default=16)

    def handle(self, *args, **options):
        plots = (
            MoviePlot.objects.order_by("movie_id")
            .select_related("movie")
            .prefetch_related("movie__genre")
        )
        if options["imdbid"]:
            plots = plots.filter(movie_id__in=options["imdbid"])
        plots = list(plots)

        # Each vector is checked against its own model name, so the two passes
        # are independent: a run cut short by --limit or an error leaves every
        # unfinished vector stale for the next run.
        texts = {PLOT: {}, PREMISE: {}}
        for plot in plots:
            premise = embeddings.premise_text(plot.movie)
            texts[PLOT][plot.pk] = (plot.text, embeddings.text_hash(plot.text))
            texts[PREMISE][plot.pk] = (
                premise,
                embeddings.text_hash(premise) if premise else "",
            )

        def stale(vector, rows):
            return [
                p
                for p in rows
                if options["force"] or is_stale(p, vector, texts[vector][p.pk][1])
            ]

        # Plot rows with empty text stay in: embedding them fails loudly.
        plot_todo = stale(PLOT, plots)
        premise_todo = stale(PREMISE, [p for p in plots if texts[PREMISE][p.pk][0]])
        empty = [p for p in plots if not texts[PREMISE][p.pk][0]]
        # No premise text: drop any vector left over from an earlier premise.
        to_clear = [p for p in empty if p.premise_embedding is not None]
        # Stale rows cut off by --limit are reported as "left", not "skipped".
        plot_stale, premise_stale, clear_stale = (
            len(plot_todo),
            len(premise_todo),
            len(to_clear),
        )
        if options["limit"] is not None:
            plot_todo = plot_todo[: options["limit"]]
            premise_todo = premise_todo[: options["limit"]]
            to_clear = to_clear[: options["limit"]]

        if not options["dry_run"]:
            # Premises first: their text is never empty, so they can't fail on
            # a bad plot row, and a plot pass error leaves them done.
            self.embed(PREMISE, premise_todo, texts[PREMISE], options["batch_size"])
            now = timezone.now()
            for plot in to_clear:
                plot.premise_embedding = None
                plot.premise_model_name = ""
                plot.premise_text_hash = ""
                plot.updated_at = now
            MoviePlot.objects.bulk_update(to_clear, PREMISE.fields)
            self.embed(PLOT, plot_todo, texts[PLOT], options["batch_size"])

        verb = "would embed" if options["dry_run"] else "embedded"
        clear_verb = "would clear" if options["dry_run"] else "cleared"
        total = len(plots)
        plot_left = plot_stale - len(plot_todo)
        premise_left = premise_stale - len(premise_todo) + clear_stale - len(to_clear)
        self.stdout.write(
            f"plot: {verb} {len(plot_todo)}, skipped {total - plot_stale}, "
            f"left {plot_left} | "
            f"premise: {verb} {len(premise_todo)}, "
            f"skipped {total - premise_stale - len(empty)}, left {premise_left}, "
            f"empty {len(empty)}, {clear_verb} {len(to_clear)} | total {total}"
        )

    def embed(self, vector, todo, texts, batch_size):
        """Embed texts[pk] for each row in todo and save the vector's fields.

        bulk_update skips auto_now, so updated_at is set by hand.
        """
        for start in range(0, len(todo), batch_size):
            batch = todo[start : start + batch_size]
            vectors = embeddings.embed_documents(
                [texts[p.pk][0] for p in batch], batch_size=batch_size
            )
            now = timezone.now()
            for plot, embedding in zip(batch, vectors):
                setattr(plot, vector.vector, embedding)
                setattr(plot, vector.model_name, embeddings.MODEL_NAME)
                setattr(plot, vector.text_hash, texts[plot.pk][1])
                plot.updated_at = now
            MoviePlot.objects.bulk_update(batch, vector.fields)
            self.stderr.write(
                f"{vector.label} embedded {start + len(batch)}/{len(todo)}"
            )
