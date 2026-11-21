# Moviechooser API

A Dockerized Django REST Framework project that provides endpoints for movie data, authentication via JSON Web Tokens, and CRUD functionality for adding movies to a user’s watch list/updating ‘watched’ state.

## Tech stack

- Python 3.12
- Django REST Framework
- Gunicorn
- Nginx
- Poetry 2.x
- PyTest
- Flake8 / Black
- Docker / Docker Compose
- Github Actions (CI/CD)
- PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`)

## Deployment

The Dockerized app is deployed to an AWS Lightsail instance via Github Actions. The database runs on the same instance as a `pgvector/pgvector:pg16` container (`mc-prod-db` in `docker-compose.prod.yml`, `mc-staging-db` for staging), reachable only on the Compose network. Its credentials live in `app/.env.prod.db` (see `app/.env.db.example`).

Lightsail's managed-database backups no longer apply, so back up with `pg_dump`. See [docs/db-cutover.md](docs/db-cutover.md) for the migration from the old Lightsail-hosted database, rollback and backups.

## Plot data and embeddings

Each movie has a `MoviePlot` row holding long-form plot text and two 384-dimension embeddings (`BAAI/bge-small-en-v1.5` via fastembed, baked into the images at `/opt/fastembed`). Two idempotent management commands build them:

- `fetch_plots` matches movies to English Wikipedia articles by IMDb ID (Wikidata property P345) and stores the article's Plot section. When there is no article or no plot section, it falls back to OMDb's full plot. Articles whose revision hasn't changed are skipped, and raw responses are cached in `app/.plot_cache/`. It needs `WIKIMEDIA_CONTACT` set to a contact address for the Wikimedia User-Agent, and `OMDB_API_KEY` for the fallback. Transient failures (HTTP 429 and 5xx, timeouts, Wikipedia `maxlag` and `ratelimited`) are retried with back-off. It ends with a summary line: `movies N | wikipedia W | omdb O | missing M | unchanged U`, where the source counts are each movie's source after the run (or what it would be, with `--dry-run`).
- `build_plot_embeddings` fills two vectors per row, and only embeds a vector when it is missing, the model has changed or its text has changed:
  - the plot vector, from `MoviePlot.text`;
  - the premise vector, from the movie's genres (sorted) plus OMDb's short plot (`Movie.plot`), e.g. `Action, Crime, Drama. A young getaway driver …`. Averaging a long plot blurs a specific premise, which is why the second vector exists. The title is deliberately left out, because title words match unrelated movies (*Baby Driver* → *Babyteeth*). Search is meant to combine the two vectors at query time.

  Each vector records its own model name, so a run that is interrupted or cut short by `--limit` is finished by the next one. It ends with `plot: embedded N, skipped S, left L, empty B, cleared A | premise: embedded P, skipped Q, left R, empty E, cleared C | total T`. `skipped` rows are already up to date, and `left` counts stale rows that `--limit` cut off, which the next run will do. For the plot, `empty` counts rows with no plot text, which are skipped so they can't stop the rest of the pass. For the premise, `empty` counts movies with neither genres nor a plot. Rows that are `empty` get no vector, and `cleared` counts old vectors removed from them in this run, so search never treats a vector from text that is gone as current. `--limit` caps embeds and clears together for each vector, embeds first.

Both take `--limit`, `--imdbid` (repeatable), `--dry-run` and `--force`. `fetch_plots` also takes `--cache-dir`, and `build_plot_embeddings` takes `--batch-size`. Re-run both after adding movies.

```bash
# dev
docker compose -f docker-compose.dev.yml exec movies python manage.py fetch_plots
docker compose -f docker-compose.dev.yml exec movies python manage.py build_plot_embeddings

# prod (on the instance, inside tmux: a full fetch takes about an hour)
docker compose -f docker-compose.prod.yml exec djangogunicorn python manage.py fetch_plots
docker compose -f docker-compose.prod.yml exec djangogunicorn python manage.py build_plot_embeddings
```

### Similar movies

`GET /api/movies/<slug>/similar/?limit=6` returns a plain array of the movies nearest to the given one, each with the usual movie fields plus `similarity`. It ranks by `0.5 × plot similarity + 0.5 × premise similarity` (1 − cosine distance for each vector), highest first, and applies the same quality bar as the movie list (average review ≥ 40, a poster). `limit` is clamped to 1–12, and anything that isn't an integer means 6. An unknown slug is a 404. A movie missing either vector, or with a vector from a different embedding model, gets `[]` and is left out of other movies' results; so does every movie until both `build_plot_embeddings` passes have run. Vectors embedded from text that has since changed are still used until the next `build_plot_embeddings` run.

### Text search

`GET /api/movies/?q=<text>` ranks the movie list by how close each movie is to a free-text description, using the same `0.5 × plot + 0.5 × premise` score as similar movies, with the query vector compared against both. The query is trimmed and cut to 120 characters, and a blank `q` behaves exactly like no `q`. Every other filter (`g`, `dmin`, `dmax`, `rmin`, `rmax`) and the quality bar still apply. The response is the usual paginated object, but it holds at most the top 30 in one page (`next` is null, `page=2` is a 404), and each item has a `similarity`. Movies missing either current-model vector are left out of text results.

Web workers embed queries with the same bge-small model (`query_embed`, which adds bge's search instruction), caching recent query vectors per worker. In prod, `config/gunicorn.py` loads the model when each worker boots, so the first search doesn't wait for it. Each worker holds its own copy, which is why prod runs 2 workers with 8 threads. If the model can't load, text queries return 503 (`Search is unavailable right now.`) and everything else keeps working.

Wikipedia text is licensed CC BY-SA. It is used only for search and is never returned by the API. Anything that shows plot text must attribute it with the stored `source_url` and `source_revid`, and link the licence. Because search and similar movies are computed from that text, every movie response carries `plot_source_url`: a permalink to the stored Wikipedia revision (`<source_url>?oldid=<source_revid>`), or `null` for OMDb plots. The app links these from "About these recommendations".

## Where to watch (TMDB)

Watch-provider data comes from TMDB, which sources it from JustWatch. It needs `TMDB_READ_TOKEN`, a TMDB v4 read-access token (TMDB account settings, then API), which is sent as a Bearer header.

### Mapping movies to TMDB

`map_tmdb_ids` looks up every movie with no `tmdb_id` using TMDB's `/find` (`external_source=imdb_id`) and stores the first **movie** result. TV-only matches and misses are logged as unmatched and retried on the next run. A movie that already has an ID is never looked up or changed, so a re-run after a full success makes no requests. One failed lookup is logged and skipped. The command ends with `mapped=N unmatched=U failed=F`, and refuses to run without a token. It takes `--limit N` and `--sleep SECONDS` (default 0.05 between requests).

```bash
# dev / your laptop
docker compose -f docker-compose.dev.yml exec movies python manage.py map_tmdb_ids --limit 20
docker compose -f docker-compose.dev.yml exec movies python manage.py map_tmdb_ids
```

On the server it runs daily at 04:00 UTC as the `map-tmdb-ids` beat job (see [Background jobs](#background-jobs)). After the first deploy, run it once by hand to backfill the catalogue.

## Posters (TMDB)

Each movie stores TMDB's `poster_path` (for example `/abc123.jpg`), and the app builds the image URL itself (`https://image.tmdb.org/t/p/w342{poster_path}`, with a `srcset` of `w185`, `w342` and `w500`). `map_tmdb_ids` saves the path from the same `/find` result that gives the ID. Movie responses carry both `poster_path` and the older OMDb `poster_url`, which the app tries second. A film with neither is still listed and shows a title placeholder. Catalogue imports only create movies, so they never overwrite a stored path.

### Checking and repairing posters

`check_posters` works in two passes:

1. **Check.** It sends a HEAD request for each stored path's `w342` image, four at a time. Connection errors, timeouts, 429 and 5xx are retried (3 tries in all). A 404 is final.
2. **Repair.** Every movie whose image is broken, and every mapped movie with no path yet, is re-read from TMDB (`/movie/{tmdb_id}`), one at a time with `--sleep SECONDS` (default 0.05) between requests. The path TMDB gives now is stored. A movie TMDB has no poster for gets a null path. A failed lookup leaves the stored path alone.

It ends with `checked=N fixed=F missing=M broken=B`:

- `checked`: paths checked in the first pass.
- `fixed`: paths stored that now load.
- `missing`: movies with no path at the end, including unmapped ones.
- `broken`: images that still don't load.

It fails (a non-zero exit, or a failed task) when `broken` is more than 5% of `checked`, and refuses to run without a token.

```bash
# dev / your laptop
docker compose -f docker-compose.dev.yml exec movies python manage.py check_posters
```

On the server it runs every Sunday at 03:00 UTC as the `check-posters` beat job (see [Background jobs](#background-jobs)). The first run is the backfill for movies mapped before `poster_path` existed: about one TMDB request per movie, which takes 10–15 minutes for the full catalogue. Run it once by hand after the first deploy, after `map_tmdb_ids`. To test a repair, set a movie's `poster_path` to something wrong in the admin and run the command again.

### Endpoints

- `GET /api/movies/<slug>/watch/?country=XX` returns `{country, available, link, providers}`. Each provider is `{provider_id, name, kind, logo}`, where `kind` is `stream` (subscription, free or ad-supported), `rent` or `buy`. Providers are ordered stream, then rent, then buy, each by TMDB's display priority.
  - `link` is TMDB's watch page for that country. If TMDB has no data for the country, it's the movie's watch page with no country.
  - `country` is any two-letter code, upper-cased, and defaults to `GB`. Anything else is a 400.
  - If TMDB can't be reached, or the movie has no `tmdb_id`, the response is still a 200, with `available: false` and no providers.
- `GET /api/watch/regions/` returns `[{code, name}]` for the countries TMDB covers, sorted by name. If TMDB is down it falls back to a short built-in list.

Movie payloads carry `has_tmdb`, and the app shows its Watch button only when it's true, so browsing never calls TMDB.

### Caching

TMDB data goes in the `tmdb` cache, Django's database cache (the `django_cache` table, created by `createcachetable` in both entrypoints). It's shared by every worker and kept across restarts. The default cache, which DRF's throttles use on every request, stays in per-process memory.

- Each movie's full TMDB response, covering every country, is kept for 24 hours, so one call serves all countries.
- A failed lookup is remembered for 60 seconds, so an outage doesn't send a request to TMDB on every panel open.
- The regions list is kept for 7 days. If TMDB can't supply it, the built-in list is served and the failure is remembered for 60 seconds.

## Background jobs

Celery runs background and scheduled work. Every compose file (dev, staging, prod) runs three extra services next to the API:

- `redis`: the broker. In prod and staging nothing is persisted, because queued messages are short-lived and beat re-queues on schedule.
- the worker (`celery` in dev, `celery-worker` in staging and prod): runs tasks. In staging and prod it runs one task at a time (`--concurrency=1`), because each worker child is a full Django process.
- `celery-beat`: queues scheduled jobs. **Run exactly one.** A second beat queues every job twice.

In staging and prod, the worker and beat override the image's entrypoint, so they never run `migrate` or start gunicorn. Only the API container does either.

Scheduled jobs are declared in one place: `CELERY_BEAT_SCHEDULE` in `config/settings/base.py`. Times are in UTC. `movies/tests/test_celery_schedule.py` fails if an entry names a task that isn't registered. The broker defaults to `redis://redis:6379/0`. Set `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` to point elsewhere.

```bash
# logs
docker compose -f docker-compose.dev.yml logs -f celery celery-beat

# is the worker up, and which tasks does it know?
docker compose -f docker-compose.dev.yml exec celery celery -A config inspect ping
docker compose -f docker-compose.dev.yml exec celery celery -A config inspect registered

# run a task by hand (or run its management command directly instead)
docker compose -f docker-compose.dev.yml exec celery celery -A config call movies.tasks.add_movies_to_db --args='[[]]'
```

In staging and prod, use the matching compose file and `celery-worker` in place of `celery`.

## Requirements

- python = "3.12"
- Django = "5.0.11"
- Django REST Framework = "3.15.1"
- Poetry = "^2.5"
- Docker = “^20.10”
- Docker Compose = “^1.29”

## How to install

1. Clone from Github

   ```bash
   cd projects
   git clone <repo-tag>
   ```

2. Add environment variables

   Create `.env` file in the root directory that includes the required variables (as listed in the .env.example file). Be careful not to commit secret/sensitive information to version control.

3. Install dependencies

   Make sure Poetry is installed and run `poetry install` to install project dependencies.

4. Start Docker container

   ```bash
   docker-compose -f docker-compose.dev.yml up -d --build
   ```

   **Upgrading from an older local database:** the dev DB is now Postgres 16, which cannot start on an existing Postgres 15 `postgres_data` volume. Before pulling this change, dump your data. Then remove the volume, start the new DB and restore:

   ```bash
   docker-compose -f docker-compose.dev.yml exec mc-dev-db pg_dump -U movies -d mc_dev -Fc -f /dump/mc_dev_pg15.dump
   docker-compose -f docker-compose.dev.yml down
   docker volume rm moviechooser-api_postgres_data
   docker-compose -f docker-compose.dev.yml up -d mc-dev-db
   docker-compose -f docker-compose.dev.yml exec mc-dev-db pg_restore -U movies -d mc_dev --no-owner /dump/mc_dev_pg15.dump
   ```

5. Run tests in Docker container

   ```bash
   docker-compose -f docker-compose.dev.yml exec movies pytest
   docker-compose -f docker-compose.dev.yml exec movies black .
   docker-compose -f docker-compose.dev.yml exec movies flake8
   docker-compose -f docker-compose.dev.yml exec movies isort .
   ```

## Featured Code

Most of the app is relatively straightforward, but one of the more interesting areas is authentication. Below is a snippet from the viewset that handles registration, checking that a Google reCaptcha submitted alongside sign-up information is valid (using a utility function).

```python
# authentication/viewsets.py

class RegisterViewSet(ModelViewSet, TokenObtainPairView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_valid_recaptcha = recaptcha_submit(
            serializer.validated_data["recaptcha_key"]
        )

        if is_valid_recaptcha:
            user_data = {}
            user_data["email"] = serializer.validated_data["email"]

            try:
                username = serializer.validated_data["username"]
                user_data["username"] = username
            except KeyError:
                pass

            user = serializer.save()
            user.is_active = True
            user_data["uid"] = str(user.uid)
            user_data["is_active"] = user.is_active

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "user": user_data,
                    "refresh": str(refresh),
                    "token": str(refresh.access_token),
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                data={"error": "ReCAPTCHA not verified."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
            )
```

The movie models involve a number of foreign key and many-to-many relationships, so I used Factory Boy to simplify creating test models, for example:

```python
# movies/tests/factories

class MovieFactory(factory.django.DjangoModelFactory):

    imdbid = factory.Sequence(lambda n: "imdb%s" % n)
    title = factory.Sequence(lambda n: "Tester %s" % n)
    released = fuzzy.FuzzyDate(datetime.date(1930, 1, 1))
    runtime = fuzzy.FuzzyInteger(50, 200)
    writer = fuzzy.FuzzyText(length=10, suffix="writer")
    poster_url = fuzzy.FuzzyText(length=10, prefix="www.", suffix="img.jpg")
    poster_path = factory.Sequence(lambda n: "/poster%s.jpg" % n)

    class Meta:
        model = Movie

class MovieWithGenreFactory(MovieFactory):
    @factory.post_generation
    def genre(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for genre in extracted:
                if Genre.objects.filter(name=genre):
                    genre = Genre.objects.get(name=genre).id
                else:
                    genre = GenreFactory(name=genre)
                self.genre.add(genre)
```

Example test:

```python
# movies/tests/test_views.py

@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range_incl_gt(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=120)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=150)
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"], runtime=240)

    resp = client.get("/api/movies/?rmin=150&rmax=>150")
    assert resp.status_code == 200
    assert "Funny Tests" not in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" in json.dumps(resp.data)
```

## Challenges and Improvements

Setting up an effective deployment pipeline to an AWS Lightsail instance (chosen to provide predictable costing) was one of the stand out challenges. In particular, successfully setting up the Nginx reverse proxy and Let’s Encrypt SSL certbot (without exceeding request limitations while testing!) were steep learning curves but very worthwhile. The database has since moved from a separate Lightsail database into a pgvector-enabled Postgres 16 container on the same instance, ready for vector search work.

In terms of further improvements (beyond adding more movies to the database), I am keen to provide further endpoints for filtering and searching content, such as by actor, director, and availability on streaming services.
