import pytest
from pytest_factoryboy import register

from movies.models import Movie

from .factories import GenreFactory, MovieFactory

register(GenreFactory)
register(MovieFactory)


@pytest.fixture(scope="function")
def add_movie():
    def _add_movie(imdbid, title, released, runtime, poster_url):
        movie = Movie.objects.create(
            imdbid=imdbid,
            title=title,
            released=released,
            runtime=runtime,
            poster_url=poster_url,
        )
        return movie

    return _add_movie
