import json
import datetime

import pytest

from .factories import GenreFactory, MovieFactory, MovieWithGenreFactory
from movies.models import Actor, Director, Genre, Movie, OnDemand, Review


@pytest.mark.django_db
def test_get_single_movie(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "-tester" in resp.data["slug"]

@pytest.mark.django_db
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
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Comedy" in resp.data["genre"][0].values()


@pytest.mark.django_db
def test_get_single_movie_with_actor(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    movie.actors.add(Actor.objects.create(name="Clem Fandango"))
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Clem Fandango" in resp.data["actors"][0].values()


@pytest.mark.django_db
def test_get_single_movie_with_director(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    director = Director.objects.create(name="Len Z")
    movie.director.add(director)
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Len Z" in resp.data["director"][0].values()


@pytest.mark.django_db
def test_get_single_movie_with_ondemand(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    ondemand = OnDemand.objects.create(
        movie=movie,
        service="Google Play",
        url="googleplay.com/"
        )
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Google Play" in resp.data["ondemand"][0].values()


@pytest.mark.django_db
def test_get_single_movie_with_review(client, add_movie):
    movie = add_movie(
        imdbid='test1234',
        title='Tester',
        released="2021-01-14",
        runtime="100",
        poster_url="www.example.com/image/location/img.jpg",
        )
    review = Review.objects.create(
        movie=movie,
        source="imdb",
        score=65
        )
    review2 = Review.objects.create(
        movie=movie,
        source="metacritic",
        score=75
        )
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "imdb" in resp.data["review"][0].values()
    assert "metacritic" in resp.data["review"][1].values()


@pytest.mark.django_db
def test_get_queryset_filtered_by_genre(client):
    # comedy = GenreFactory.create(name="comedy")
    # movie1 = MovieFactory.create(
    #     title="Funny Tests",
    #     genre=[comedy]
    # )
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"]
    )
    horror = GenreFactory.create(name="horror")
    movie2 = MovieFactory.create(
        title="Scary Tests",
        genre=[horror]
    )
    print("movie.genre >>>", movie1.__dict__)
    print("movie1.genre >>>", movie1.genre.all())
    qs = movie1.genre.all()
    qs_names = [genre.name for genre in qs]
    assert movie1.title == "Funny Tests"
    assert ["comedy"] == qs_names

    # resp = client.get(f"/api/movies?genre=1/")
    # assert resp.status_code == 200
    # assert resp.data["title"] == "Funny Tests"