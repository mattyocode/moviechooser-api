from collections import OrderedDict
import datetime

import pytest

from movies.serializers import (
    ActorSerializer, 
    DirectorSerializer, 
    GenreSerializer, 
    MovieSerializer, 
    OnDemandSerializer, 
    ReviewSerializer
)


@pytest.mark.django_db
def test_valid_movie_serializer():
    released_date = datetime.date(2021, 1, 14)
    valid_serializer_data = {
        'title': 'Tester: Revenge of the Test',
        'slug': '1a2b3c4d-tester',
        'released': released_date,
        'runtime': 100,
        'writer': 'Check Itt', 
        'plot': 'Once upon a time...',
        'country': 'UK', 
        'poster_url': 'www.example.com/image/location/img.jpg',
    }
    serializer = MovieSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data

    valid_serializer_data['released'] = '2021-01-14'
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}


def test_invalid_movie_serializer():
    invalid_serializer_data = {
        'title': 'Tester: Revenge of the Test',
    }
    serializer = MovieSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "poster_url": ["This field is required."],
        "released": ["This field is required."],
        "writer": ["This field is required."],
        }


@pytest.mark.django_db
def test_valid_genre_serializer():
    valid_serializer_data = {
        'name': 'Comedy',
    }
    serializer = GenreSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}


def test_invalid_genre_serializer():
    invalid_serializer_data = {}
    serializer = GenreSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "name": ["This field is required."],
        }


@pytest.mark.django_db
def test_valid_actor_serializer():
    valid_serializer_data = {
        'name': 'Clem Fandango',
    }
    serializer = ActorSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}


def test_invalid_actor_serializer():
    invalid_serializer_data = {}
    serializer = ActorSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "name": ["This field is required."],
        }


@pytest.mark.django_db
def test_valid_director_serializer():
    valid_serializer_data = {
        'name': 'Len Z',
    }
    serializer = DirectorSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}


def test_invalid_director_serializer():
    invalid_serializer_data = {}
    serializer = DirectorSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "name": ["This field is required."],
        }


@pytest.mark.django_db
def test_valid_ondemand_serializer(add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
    )
    valid_serializer_data = {
        "movie": movie.imdbid,
        "service": "Google Play",
        "url": "googleplay.com/"
    }
    serializer = OnDemandSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.data == valid_serializer_data

    valid_serializer_data["movie"] = movie
    assert serializer.validated_data == valid_serializer_data
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_ondemand_serializer(add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
    )
    invalid_serializer_data = {
        'movie': movie.imdbid,
    }
    serializer = OnDemandSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "service": ["This field is required."],
        "url": ["This field is required."],
        }


@pytest.mark.django_db
def test_valid_review_serializer(add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
    )
    valid_serializer_data = {
        "movie": movie.imdbid,
        "source": "imdb",
        "score": 65
    }
    serializer = ReviewSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.data == valid_serializer_data

    valid_serializer_data["movie"] = movie
    assert serializer.validated_data == valid_serializer_data
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_review_serializer(add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
    )
    invalid_serializer_data = {
        'movie': movie.imdbid,
    }
    serializer = ReviewSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "source": ["This field is required."],
        "score": ["This field is required."],
        }