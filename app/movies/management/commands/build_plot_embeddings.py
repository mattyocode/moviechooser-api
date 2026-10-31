from django.core.management.base import BaseCommand

from movies import embeddings
from movies.models import MoviePlot


def needs_embedding(plot: MoviePlot) -> bool:
    return (
        plot.embedding is None
        or plot.model_name != embeddings.MODEL_NAME
        or plot.embedded_text_hash != embeddings.text_hash(plot.text)
    )


def needs_premise_embedding(plot: MoviePlot, text: str) -> bool:
    return bool(text) and (
        plot.premise_embedding is None
        or plot.model_name != embeddings.MODEL_NAME
        or plot.premise_text_hash != embeddings.text_hash(text)
    )


class Command(BaseCommand):
    help = (
        "Embed MoviePlot text and each movie's premise (genres plus OMDb short "
        "plot). Only rows with no embedding, a different model or changed text "
        "are embedded, so re-running is cheap."
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

        # Both work lists come from one snapshot, before the plot pass rewrites
        # model_name, so a model change re-embeds both vectors. They share the
        # order and --limit, so the plot pass never moves a row to a new model
        # without the premise pass re-embedding it too.
        premises = {p.pk: embeddings.premise_text(p.movie) for p in plots}
        plot_todo = [p for p in plots if options["force"] or needs_embedding(p)]
        premise_todo = [
            p
            for p in plots
            if (options["force"] and premises[p.pk])
            or needs_premise_embedding(p, premises[p.pk])
        ]
        if options["limit"] is not None:
            plot_todo = plot_todo[: options["limit"]]
            premise_todo = premise_todo[: options["limit"]]
        # No premise text: drop any vector left over from an earlier premise.
        empty = [p for p in plots if not premises[p.pk]]

        if not options["dry_run"]:
            self.embed_plots(plot_todo, options["batch_size"])
            self.embed_premises(premise_todo, premises, options["batch_size"])
            stale = [p for p in empty if p.premise_embedding is not None]
            for plot in stale:
                plot.premise_embedding = None
                plot.premise_text_hash = ""
            MoviePlot.objects.bulk_update(
                stale, ["premise_embedding", "premise_text_hash"]
            )

        verb = "would embed" if options["dry_run"] else "embedded"
        total = len(plots)
        self.stdout.write(
            f"plot: {verb} {len(plot_todo)}, skipped {total - len(plot_todo)} | "
            f"premise: {verb} {len(premise_todo)}, "
            f"skipped {total - len(premise_todo) - len(empty)}, "
            f"empty {len(empty)} | total {total}"
        )

    def embed_plots(self, todo, batch_size):
        for start in range(0, len(todo), batch_size):
            batch = todo[start : start + batch_size]
            vectors = embeddings.embed_documents(
                [p.text for p in batch], batch_size=batch_size
            )
            for plot, vector in zip(batch, vectors):
                plot.embedding = vector
                plot.model_name = embeddings.MODEL_NAME
                plot.embedded_text_hash = embeddings.text_hash(plot.text)
            MoviePlot.objects.bulk_update(
                batch, ["embedding", "model_name", "embedded_text_hash"]
            )
            self.stderr.write(f"plot embedded {start + len(batch)}/{len(todo)}")

    def embed_premises(self, todo, premises, batch_size):
        for start in range(0, len(todo), batch_size):
            batch = todo[start : start + batch_size]
            texts = [premises[p.pk] for p in batch]
            vectors = embeddings.embed_documents(texts, batch_size=batch_size)
            for plot, text, vector in zip(batch, texts, vectors):
                plot.premise_embedding = vector
                plot.premise_text_hash = embeddings.text_hash(text)
            MoviePlot.objects.bulk_update(
                batch, ["premise_embedding", "premise_text_hash"]
            )
            self.stderr.write(f"premise embedded {start + len(batch)}/{len(todo)}")
