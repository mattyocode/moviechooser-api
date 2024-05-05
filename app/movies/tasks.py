import random
import time

from django.db import transaction
from celery import Task, chain
from config.celery import app

from .models import Actor, Director, Genre, Movie, Review
from .utils import OMDBFetch, get_imdbids_from_webpage

# from celery.utils.log import get_task_logger


# logger = get_task_logger(__name__)


class DelayedTask(Task):
    """Include a 1-2 second delay between requests to prevent rate limiting."""

    def run(self, *args, **kwargs):
        time.sleep(random.randint(1, 2))
        return super().run(*args, **kwargs)


@app.task(base=DelayedTask)
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


def execute_tasks_sequentially(imdbids):
    # Create a chain of tasks
    task_chain = chain(add_movie_to_db.s(imdbid) for imdbid in imdbids)
    # Execute the chain synchronously
    result = task_chain.apply_async()
    # Wait for the result
    result.get()


def add_movies_from_url_to_db(url: str):
    imdbids = get_imdbids_from_webpage(url)
    execute_tasks_sequentially(imdbids)
