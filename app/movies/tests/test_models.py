import pytest

from movies.models import Actor, Director, Genre, Movie, OnDemand, Review


@pytest.mark.django_db
def test_movie_model():
    movie = Movie(
        imdbid="test1234",
        title="Tester: Revenge of the Test",
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
    assert movie.slug
    assert str(movie) == movie.title


@pytest.mark.django_db
def test_actor_model():
    actor = Actor(name="Clem Fandango")
    actor.save()

    assert actor.name == "Clem Fandango"
    assert str(actor) == actor.name


@pytest.mark.django_db
def test_director_model():
    director = Director(name="Len Z")
    director.save()

    assert director.name == "Len Z"
    assert str(director) == director.name


@pytest.mark.django_db
def test_genre_model():
    genre = Genre(name="Comedy")
    genre.save()

    assert genre.name == "Comedy"
    assert str(genre) == genre.name


@pytest.mark.django_db
def test_ondemand_model(add_movie):
    movie = Movie(
        imdbid="test1234",
        title="Tester: Revenge of the Test",
        rated="PG",
        released="2021-01-14",
    )
    movie.save()
    ondemand = OnDemand(
        movie=movie,
        service="Google Play",
        url="googleplay.com/",
    )
    ondemand.save()

    assert ondemand.movie.imdbid == "test1234"
    assert ondemand.service == "Google Play"
    assert ondemand.url == "googleplay.com/"
    assert ondemand.added
    assert ondemand.updated
    assert str(ondemand) == ondemand.movie.imdbid + "--" + ondemand.service


@pytest.mark.django_db
def test_review_model(add_movie):
    movie = Movie(
        imdbid="test1234",
        title="Tester: Revenge of the Test",
        rated="PG",
        released="2021-01-14",
    )
    movie.save()
    review = Review(
        movie=movie,
        source="imdb",
        score=65,
    )
    review.save()

    assert review.movie.imdbid == "test1234"
    assert review.source == "imdb"
    assert review.score == 65
    assert str(review) == review.source + "--" + str(review.score)
