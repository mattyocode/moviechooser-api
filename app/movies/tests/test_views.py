import json

import pytest

from movies.models import Genre, Movie


@pytest.mark.django_db
def test_get_single_movie(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    resp = client.get(f"/api/movies/{movie.id}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"


def test_get_single_movie_incorrect_id(client):
    resp = client.get("/api/movies/foo/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_get_all_movies(client, add_movie):
    movie_one = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    movie_two = add_movie(
        imdbid='test0987',
        title='Test 2: Revenge of the Test',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    resp = client.get(f"/api/movies/")
    assert resp.status_code == 200
    assert resp.data[0]["title"] == movie_one.title
    assert resp.data[1]["title"] == movie_two.title


@pytest.mark.django_db
def test_get_single_movie_with_genre(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    movie.genre.add(Genre.objects.create(name="Comedy"))
    resp = client.get(f"/api/movies/{movie.id}/")
    print("resp >>", resp.data)
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"