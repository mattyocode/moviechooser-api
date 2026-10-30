from django.core.management.base import BaseCommand

from movies import embeddings
from movies.models import MoviePlot


def needs_embedding(plot: MoviePlot) -> bool:
    return (
        plot.embedding is None
        or plot.model_name != embeddings.MODEL_NAME
        or plot.embedded_text_hash != embeddings.text_hash(plot.text)
    )


class Command(BaseCommand):
    help = (
        "Embed MoviePlot text. Only rows with no embedding, a different model "
        "or changed text are embedded, so re-running is cheap."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Embed at most N rows.")
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
        plots = MoviePlot.objects.order_by("movie_id")
        if options["imdbid"]:
            plots = plots.filter(movie_id__in=options["imdbid"])

        total = plots.count()
        todo = [p for p in plots.iterator() if options["force"] or needs_embedding(p)]
        if options["limit"] is not None:
            todo = todo[: options["limit"]]

        if not options["dry_run"]:
            batch_size = options["batch_size"]
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
                self.stderr.write(f"embedded {start + len(batch)}/{len(todo)}")

        verb = "would embed" if options["dry_run"] else "embedded"
        self.stdout.write(
            f"{verb} {len(todo)} | skipped {total - len(todo)} | total {total}"
        )
