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

  Each vector records its own model name, so a run that is interrupted or cut short by `--limit` is finished by the next one. It ends with `plot: embedded N, skipped S, left L, empty B | premise: embedded P, skipped Q, left R, empty E, cleared C | total T`. `skipped` rows are already up to date, and `left` counts stale rows that `--limit` cut off, which the next run will do. For the plot, `empty` counts rows with no plot text, which are skipped so they can't stop the rest of the pass. For the premise, `empty` counts movies with neither genres nor a plot, which get no premise vector, and `cleared` counts old premise vectors removed from those movies in this run.

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

Wikipedia text is licensed CC BY-SA. It is used only for search and is never returned by the API. Anything that shows plot text must attribute it with the stored `source_url` and `source_revid`, and link the licence.

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
