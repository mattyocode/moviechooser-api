import logging
import random
import time

from celery import Task, chain
from config.celery import app
from django.db import transaction

from .models import Actor, Director, Genre, Movie, Review
from .utils import OMDBFetch, get_imdbids_from_webpage

log = logging.Logger(__name__)


@transaction.atomic
def add_movie_to_db(imdbid):
    omdb_data = OMDBFetch(imdbid).get_data()

    related_actors = []
    actors = [a.strip() for a in omdb_data["Actors"].split(",")]
    for actor in actors:
        obj, _ = Actor.objects.get_or_create(name=actor)
        related_actors.append(obj.id)

    related_directors = []
    directors = [d.strip() for d in omdb_data["Director"].split(",")]
    for director in directors:
        obj, _ = Director.objects.get_or_create(name=director)
        related_directors.append(obj.id)

    related_genres = []
    genres = [g.strip() for g in omdb_data["Genre"].split(",")]
    for genre in genres:
        obj, _ = Genre.objects.get_or_create(name=genre)
        related_genres.append(obj.id)

    movie = Movie.objects.create(
        imdbid=omdb_data["imdbID"],
        title=omdb_data["Title"],
        rated=omdb_data["Rated"],
        released=omdb_data["Released"],
        runtime=omdb_data["Runtime"],
        writer=omdb_data["Writer"],
        plot=omdb_data["Plot"],
        language=omdb_data["Language"],
        country=omdb_data["Country"],
        poster_url=omdb_data["Poster"],
    )

    movie.actors.set(related_actors)
    movie.director.set(related_directors)
    movie.genre.set(related_genres)

    for source, score in omdb_data["Ratings"].items():
        Review.objects.create(movie=movie, source=source, score=score)


@app.task()
def add_movies_to_db(imdbids):
    """Task to add a list of movies to DB."""
    # Execute tasks sequentially to prevent rate limiting.
    for imdbid in imdbids:
        try:
            add_movie_to_db(imdbid)
        except Exception as e:
            log.error(f"Failed to add {imdbid}")
        print(f"Added {imdbid} to DB.")
        log.info(f"Successfully added {imdbid} to DB.")
        time.sleep(random.randint(1, 2))


def add_movies_from_url_to_db(url: str):
    new_movie_ids = set(get_imdbids_from_webpage(url))
    current_ids = set(Movie.objects.all().values_list("imdbid", flat=True))
    movies_to_add = new_movie_ids - current_ids
    add_movies_to_db(list(movies_to_add))
