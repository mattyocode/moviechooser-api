import logging
import random
import time

from django.conf import settings
from django.db import transaction

from config.celery import app

from . import posters, tmdb_mapping
from .models import Actor, Director, Genre, Movie, Review
from .utils import OMDBFetch, get_imdbids_from_webpage

logger = logging.getLogger(__name__)

# check_posters stops starting new work this many seconds in, leaving five
# minutes for in-flight requests and the summary before the hard limit.
POSTER_TIME_BUDGET = settings.CELERY_TASK_TIME_LIMIT - 5 * 60


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
            logger.error(f"Failed to add {imdbid}: {e}")
        print(f"Added {imdbid} to DB.")
        logger.info(f"Successfully added {imdbid} to DB.")
        time.sleep(random.randint(1, 2))


def add_movies_from_url_to_db(url: str):
    new_movie_ids = set(get_imdbids_from_webpage(url))
    current_ids = set(Movie.objects.all().values_list("imdbid", flat=True))
    movies_to_add = new_movie_ids - current_ids
    add_movies_to_db(list(movies_to_add))


@app.task()
def map_tmdb_ids():
    """Daily: link newly added movies to TMDB IDs.

    Returns the counts, so they show in the result backend and worker log.
    A missing token raises TMDBNotConfigured, failing the task visibly.
    """
    result = tmdb_mapping.map_tmdb_ids()
    logger.info("map_tmdb_ids: %s", result)
    return result.as_dict()


@app.task()
def check_posters():
    """Weekly: check every TMDB poster loads, and repair broken and missing
    paths.

    Returns the counts, so they show in the result backend and worker log.
    Stops starting new work POSTER_TIME_BUDGET seconds in, so it finishes
    before Celery's hard time limit kills it. Raises PosterCheckFailed
    (after logging the summary) when the result has a problem (too many
    still broken, or out of time), and TMDBNotConfigured without a token,
    failing the task visibly either way.
    """
    result = posters.check_posters(time_budget=POSTER_TIME_BUDGET)
    logger.info("check_posters: %s", result)
    if problem := result.problem():
        logger.error("check_posters: %s", problem)
        raise posters.PosterCheckFailed(problem)
    return result.as_dict()
