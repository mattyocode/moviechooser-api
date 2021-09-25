import pytest

from movies.models import Movie

@pytest.mark.django_db
def test_movie_model():
    movie = Movie(
        imdbid='test1234',
        title='Tester: Revenge of the Test',
        rated="PG",
        released="2021-01-14",
        runtime="100",
        writer="Check Itt", 
        plot="Once upon a time...", 
        language="English", 
        country="UK", 
        poster_url="www.example.com/image/location/img.jpg",
        type_field="movie",
    )
    movie.save()

    assert movie.imdbid == "test1234"
    assert movie.title == "Tester: Revenge of the Test"
    assert movie.rated == "PG"
    assert movie.released == "2021-01-14"
    assert movie.runtime == "100"
    assert movie.writer == "Check Itt"
    assert movie.plot == "Once upon a time..."
    assert movie.language == "English"
    assert movie.country == "UK"
    assert movie.poster_url == "www.example.com/image/location/img.jpg"
    assert movie.type_field == "movie"
    assert str(movie) == movie.title