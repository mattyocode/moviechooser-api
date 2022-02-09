# Moviechooser API

A Dockerized Django REST Framework project that provides endpoints for movie data, authentication via JSON Web Tokens, and CRUD functionality for adding movies to a user’s watch list/updating ‘watched’ state.

## Tech stack

- Python
- Django REST Framework
- Gunicorn
- Nginx
- Poetry
- PyTest
- Flake8 / Black
- Docker / Docker Compose
- Github Actions (CI/CD)
- PostgreSQL

## Deployment

The Dockerized app is deployed to an AWS Lightsail instance via Github Actions. The database is also hosted on Lightsail.

## Requirements

- python = "^3.9"
- Django = "3.2.7"
- Django REST Framework = "3.12.4"
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

Setting up an effective deployment pipeline to an AWS Lightsail instance (chosen to provide predictable costing) was one of the stand out challenges. In particular, successfully setting up the Nginx reverse proxy and Let’s Encrypt SSL certbot (without exceeding request limitations while testing!) were steep learning curves but very worthwhile.

In terms of further improvements (beyond adding more movies to the database), I am keen to provide further endpoints for filtering and searching content, such as by actor, director, and availability on streaming services.
