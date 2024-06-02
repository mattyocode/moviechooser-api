import pytest
from movies.models import Movie
from pytest_factoryboy import register

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


@pytest.fixture
def mock_requests_get(mocker):
    mock = mocker.patch("requests.get")
    mock.return_value.__enter__.return_value.json.return_value = {
        "Title": "No Sudden Move",
        "Year": "2021",
        "Rated": "R",
        "Released": "01 Jul 2021",
        "Runtime": "999 min",
        "Genre": "Crime, Drama, Mystery",
        "Director": "Steven Soderbergh",
        "Writer": "Ed Solomon",
        "Actors": "Don Cheadle, Benicio Del Toro, David Harbour",
        "Plot": "A group of criminals are brought together under mysterious circumstances \
            and have to work together to uncover what's really going on when their simple \
            job goes completely sideways.",
        "Language": "English",
        "Country": "United States",
        "Awards": "N/A",
        "Poster": "https://m.media-amazon.com/images/M/MV5BNWI2ZDQxZDQtZDMxZi00ZWFhLTg1OGYtYmFk\
            MjRkMDc2NDNkXkEyXkFqcGdeQXVyMTkxNjUyNQ@@._V1_SX300.jpg",
        "Ratings": [
            {"Source": "Internet Movie Database", "Value": "6.5/10"},
            {"Source": "Rotten Tomatoes", "Value": "91%"},
            {"Source": "Metacritic", "Value": "76/100"},
        ],
        "Metascore": "76",
        "imdbRating": "6.5",
        "imdbVotes": "19,435",
        "imdbID": "tt11525644",
        "Type": "movie",
        "DVD": "01 Jul 2021",
        "BoxOffice": "N/A",
        "Production": "HBO Max, Warner Max, Warner Bros.",
        "Website": "N/A",
        "Response": "True",
    }
    return mock
