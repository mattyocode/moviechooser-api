from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from movies import plot_sources
from movies.models import Movie, MoviePlot, PlotSource


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
            "--dry-run", action="store_true", help="Fetch, but write nothing."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-fetch even when the article revision is unchanged.",
        )
        parser.add_argument(
            "--cache-dir",
            default=str(settings.APP_BASE_DIR / ".plot_cache"),
            help="Where raw Wikipedia responses are cached.",
        )

    def handle(self, *args, **options):
        try:
            client = plot_sources.make_client()
        except plot_sources.PlotSourceError as e:
            raise CommandError(str(e))

        movies = Movie.objects.order_by("imdbid")
        if options["imdbid"]:
            movies = movies.filter(imdbid__in=options["imdbid"])
        if options["limit"] is not None:
            movies = movies[: options["limit"]]
        movies = list(movies)
        existing = MoviePlot.objects.in_bulk([m.imdbid for m in movies])

        titles = plot_sources.imdb_to_titles(client, [m.imdbid for m in movies])
        revisions = plot_sources.latest_revisions(client, titles.values())

        self.no_article, self.no_section, self.errors = [], [], []
        self.unchanged = 0
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
            if i % 50 == 0:
                self.stderr.write(f"processed {i}/{len(movies)}")

        self.report(movies, options["dry_run"])

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
            extract = plot_sources.fetch_extract(
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
        # The embedding is kept: build_plot_embeddings sees the text hash change.
        if not dry_run:
            MoviePlot.objects.update_or_create(movie=movie, defaults=fields)

    def report(self, movies, dry_run):
        plots = MoviePlot.objects.filter(movie__in=movies)
        wikipedia = plots.filter(source=PlotSource.WIKIPEDIA).count()
        omdb = plots.filter(source=PlotSource.OMDB).count()
        missing = len(movies) - wikipedia - omdb

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
            f"{prefix}movies {len(movies)} | wikipedia {wikipedia} | omdb {omdb} | "
            f"missing {missing} | unchanged {self.unchanged}"
        )
