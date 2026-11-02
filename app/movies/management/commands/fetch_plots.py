from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from movies import plot_sources
from movies.models import Movie, MoviePlot, PlotSource

# A source that fails this many movies in a row is down: stop instead of
# retrying it for every remaining movie.
MAX_ERRORS_IN_A_ROW = 20


class Command(BaseCommand):
    help = (
        "Fetch each movie's plot from English Wikipedia (matched on IMDb ID through "
        "Wikidata), falling back to OMDb, into MoviePlot. Unchanged articles are "
        "skipped, so re-running is cheap."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Only the first N movies.")
        parser.add_argument(
            "--imdbid", action="append", help="Only this movie (repeatable)."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch, but don't write to the database. The response cache is "
            "still filled.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-process every movie, even when its article revision is "
            "unchanged. Wikipedia responses cached for that revision are reused; "
            "delete --cache-dir to fetch them again.",
        )
        parser.add_argument(
            "--cache-dir",
            default=str(settings.APP_BASE_DIR / ".plot_cache"),
            help="Where raw Wikipedia responses are cached.",
        )

    def handle(self, *args, **options):
        movies = Movie.objects.order_by("imdbid")
        if options["imdbid"]:
            movies = movies.filter(imdbid__in=options["imdbid"])
        if options["limit"] is not None:
            movies = movies[: options["limit"]]
        movies = list(movies)
        existing = MoviePlot.objects.only("source", "source_revid").in_bulk(
            [m.imdbid for m in movies]
        )

        try:
            client = plot_sources.make_client()
            # Without a key every fallback would store the short plot as OMDb's,
            # and later runs would treat it as final.
            plot_sources.omdb_api_key()
            titles = plot_sources.imdb_to_titles(client, [m.imdbid for m in movies])
            revisions = plot_sources.latest_revisions(client, titles.values())
        except plot_sources.PlotSourceError as e:
            raise CommandError(str(e))

        self.no_article, self.no_section, self.errors = [], [], []
        self.unchanged = 0
        # Each movie's source once this run is done (or would be, for --dry-run).
        self.sources = {imdbid: plot.source for imdbid, plot in existing.items()}
        in_a_row = 0
        for i, movie in enumerate(movies, 1):
            try:
                self.update_movie(
                    client,
                    movie,
                    existing.get(movie.imdbid),
                    titles,
                    revisions,
                    options,
                )
            except Exception as e:
                self.errors.append(movie.imdbid)
                self.stderr.write(f"{movie.imdbid}: {e}")
                in_a_row += 1
                if in_a_row == MAX_ERRORS_IN_A_ROW:
                    self.report(len(movies), options["dry_run"])
                    raise CommandError(
                        f"Stopped after {in_a_row} failures in a row, at movie "
                        f"{i}/{len(movies)}. Last error: {e}"
                    )
            else:
                in_a_row = 0
            if i % 50 == 0:
                self.stderr.write(f"processed {i}/{len(movies)}")

        self.report(len(movies), options["dry_run"])

    def update_movie(self, client, movie, plot, titles, revisions, options):
        title = titles.get(movie.imdbid)
        resolved, revid = revisions.get(title, (None, None))

        if revid is not None:
            if (
                not options["force"]
                and plot
                and plot.source == PlotSource.WIKIPEDIA
                and plot.source_revid == revid
            ):
                self.unchanged += 1
                return
            extract, revid = plot_sources.fetch_extract(
                client, resolved, revid, options["cache_dir"]
            )
            text = plot_sources.extract_plot_section(extract)
            if text:
                self.save(
                    movie,
                    options["dry_run"],
                    source=PlotSource.WIKIPEDIA,
                    text=text,
                    source_url=plot_sources.article_url(resolved),
                    source_revid=revid,
                )
                return
            self.no_section.append(movie.imdbid)
        else:
            self.no_article.append(movie.imdbid)

        if plot and plot.source == PlotSource.OMDB and not options["force"]:
            self.unchanged += 1
            return
        text = plot_sources.fetch_omdb_plot(client, movie.imdbid) or movie.plot
        text = (text or "").strip()
        if text and text != "N/A":
            self.save(
                movie,
                options["dry_run"],
                source=PlotSource.OMDB,
                text=text,
                source_url=plot_sources.IMDB_TITLE_URL.format(imdbid=movie.imdbid),
                source_revid=None,
            )

    def save(self, movie, dry_run, **fields):
        self.sources[movie.imdbid] = fields["source"]
        # The embedding is kept: build_plot_embeddings sees the text hash change.
        if not dry_run:
            MoviePlot.objects.update_or_create(movie=movie, defaults=fields)

    def report(self, total, dry_run):
        sources = list(self.sources.values())
        wikipedia = sources.count(PlotSource.WIKIPEDIA)
        omdb = sources.count(PlotSource.OMDB)
        missing = total - wikipedia - omdb

        if self.no_article:
            self.stdout.write(
                f"no article ({len(self.no_article)}): {' '.join(self.no_article)}"
            )
        if self.no_section:
            self.stdout.write(
                f"no plot section ({len(self.no_section)}): {' '.join(self.no_section)}"
            )
        if self.errors:
            self.stdout.write(f"errors ({len(self.errors)}): {' '.join(self.errors)}")
        prefix = "dry run, nothing written | " if dry_run else ""
        self.stdout.write(
            f"{prefix}movies {total} | wikipedia {wikipedia} | omdb {omdb} | "
            f"missing {missing} | unchanged {self.unchanged}"
        )
