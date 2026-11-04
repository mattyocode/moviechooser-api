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


class Pass(NamedTuple):
    """One vector's share of a run."""

    todo: list
    clear: list
    skipped: int
    left: int
    empty: int


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

        passes = {
            vector: self.plan(vector, plots, texts[vector], options)
            for vector in (PLOT, PREMISE)
        }

        if not options["dry_run"]:
            for vector in (PREMISE, PLOT):
                self.embed(
                    vector, passes[vector].todo, texts[vector], options["batch_size"]
                )
                self.clear(vector, passes[vector].clear)

        verb = "would embed" if options["dry_run"] else "embedded"
        clear_verb = "would clear" if options["dry_run"] else "cleared"
        reports = [
            f"{vector.label}: {verb} {len(p.todo)}, skipped {p.skipped}, "
            f"left {p.left}, empty {p.empty}, {clear_verb} {len(p.clear)}"
            for vector, p in passes.items()
        ]
        self.stdout.write(" | ".join(reports + [f"total {len(plots)}"]))

    def plan(self, vector, plots, texts, options):
        """Which rows this run embeds and clears for one vector."""
        # Rows with no text can't be embedded: count them as "empty" so one bad
        # row doesn't stop the rest of the pass.
        with_text = [p for p in plots if texts[p.pk][0].strip()]
        todo = [
            p
            for p in with_text
            if options["force"] or is_stale(p, vector, texts[p.pk][1])
        ]
        # No text: drop any vector left over from earlier text.
        clear = [
            p
            for p in plots
            if not texts[p.pk][0].strip() and getattr(p, vector.vector) is not None
        ]
        skipped = len(with_text) - len(todo)
        stale = len(todo) + len(clear)
        # Embeds and clears share --limit; rows it cuts off are reported as
        # "left", not "skipped".
        if options["limit"] is not None:
            todo = todo[: options["limit"]]
            clear = clear[: options["limit"] - len(todo)]
        return Pass(
            todo=todo,
            clear=clear,
            skipped=skipped,
            left=stale - len(todo) - len(clear),
            empty=len(plots) - len(with_text),
        )

    def clear(self, vector, todo):
        """Remove the vector from each row in todo; it has no text to embed."""
        now = timezone.now()
        for plot in todo:
            setattr(plot, vector.vector, None)
            setattr(plot, vector.model_name, "")
            setattr(plot, vector.text_hash, "")
            plot.updated_at = now
        MoviePlot.objects.bulk_update(todo, vector.fields)

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
