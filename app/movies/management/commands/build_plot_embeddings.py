from django.core.management.base import BaseCommand

from movies import embeddings
from movies.models import MoviePlot


def is_stale(vector, model_name: str, stored_hash: str, current_hash: str) -> bool:
    return (
        vector is None
        or model_name != embeddings.MODEL_NAME
        or stored_hash != current_hash
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
        premises = {}
        for plot in plots:
            text = embeddings.premise_text(plot.movie)
            premises[plot.pk] = (text, embeddings.text_hash(text) if text else "")

        plot_todo = [
            p
            for p in plots
            if options["force"]
            or is_stale(
                p.embedding,
                p.model_name,
                p.embedded_text_hash,
                embeddings.text_hash(p.text),
            )
        ]
        premise_todo = [
            p
            for p in plots
            if premises[p.pk][0]
            and (
                options["force"]
                or is_stale(
                    p.premise_embedding,
                    p.premise_model_name,
                    p.premise_text_hash,
                    premises[p.pk][1],
                )
            )
        ]
        empty = [p for p in plots if not premises[p.pk][0]]
        # No premise text: drop any vector left over from an earlier premise.
        to_clear = [p for p in empty if p.premise_embedding is not None]
        if options["limit"] is not None:
            plot_todo = plot_todo[: options["limit"]]
            premise_todo = premise_todo[: options["limit"]]
            to_clear = to_clear[: options["limit"]]

        if not options["dry_run"]:
            self.embed_plots(plot_todo, options["batch_size"])
            self.embed_premises(premise_todo, premises, options["batch_size"])
            for plot in to_clear:
                plot.premise_embedding = None
                plot.premise_model_name = ""
                plot.premise_text_hash = ""
            MoviePlot.objects.bulk_update(
                to_clear,
                ["premise_embedding", "premise_model_name", "premise_text_hash"],
            )

        verb = "would embed" if options["dry_run"] else "embedded"
        clear_verb = "would clear" if options["dry_run"] else "cleared"
        total = len(plots)
        self.stdout.write(
            f"plot: {verb} {len(plot_todo)}, skipped {total - len(plot_todo)} | "
            f"premise: {verb} {len(premise_todo)}, "
            f"skipped {total - len(premise_todo) - len(empty)}, "
            f"empty {len(empty)}, {clear_verb} {len(to_clear)} | total {total}"
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
            vectors = embeddings.embed_documents(
                [premises[p.pk][0] for p in batch], batch_size=batch_size
            )
            for plot, vector in zip(batch, vectors):
                plot.premise_embedding = vector
                plot.premise_model_name = embeddings.MODEL_NAME
                plot.premise_text_hash = premises[plot.pk][1]
            MoviePlot.objects.bulk_update(
                batch,
                ["premise_embedding", "premise_model_name", "premise_text_hash"],
            )
            self.stderr.write(f"premise embedded {start + len(batch)}/{len(todo)}")
