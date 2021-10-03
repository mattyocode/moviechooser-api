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
    assert movie_one.title in json.dumps(resp.data)
    assert movie_two.title in json.dumps(resp.data)


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
    assert "Comedy" in json.dumps(resp.data)


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
    assert "Clem Fandango" in json.dumps(resp.data)


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
    assert "Len Z" in json.dumps(resp.data)


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
    assert "Google Play" in json.dumps(resp.data)


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
    assert "imdb" in resp.data["reviews"][0].values()
    assert "metacritic" in resp.data["reviews"][1].values()


@pytest.mark.django_db
def test_get_queryset_filtered_by_genre(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"]
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"]
    )

    comedy_id = movie1.genre.get(name="comedy").id

    resp = client.get(f"/api/movies/?g={comedy_id}")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_2_genres(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"]
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"]
    )
    movie3 = MovieWithGenreFactory.create(
        title="Tense Tests",
        genre=["thriller"]
    )

    comedy_id = movie1.genre.get(name="comedy").id
    horror_id = movie2.genre.get(name="horror").id

    resp = client.get(f"/api/movies/?g={comedy_id}&g={horror_id}")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_single_decade(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        released = datetime.date(1990, 1, 1)
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        released = datetime.date(1989, 12, 31)
    )

    resp = client.get(f"/api/movies/?dmin=1990&dmax=1990")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_decade_range(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        released = datetime.date(1990, 1, 1)
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        released = datetime.date(1985, 12, 31)
    )
    movie3 = MovieWithGenreFactory.create(
        title="Tense Tests",
        genre=["thriller"],
        released = datetime.date(2000, 1, 1)
    )

    resp = client.get(f"/api/movies/?dmin=1980&dmax=1990")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        runtime = 90
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        runtime = 120
    )

    resp = client.get(f"/api/movies/?rmin=90&rmax=90")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        runtime = 90
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        runtime = 120
    )
    movie3 = MovieWithGenreFactory.create(
        title="Tense Tests",
        genre=["thriller"],
        runtime = 150
    )

    resp = client.get(f"/api/movies/?rmin=90&rmax=120")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_all_criteria(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        released = datetime.date(1985, 1, 1),
        runtime = 90
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        released = datetime.date(2000, 1, 1),
        runtime = 120
    )
    movie3 = MovieWithGenreFactory.create(
        title="Tense Tests",
        genre=["thriller"],
        released = datetime.date(1990, 1, 1),
        runtime = 150
    )
    movie4 = MovieWithGenreFactory.create(
        title="Even Funnier Tests",
        genre=["comedy"],
        released = datetime.date(1990, 1, 1),
        runtime = 155
    )

    comedy_id = movie1.genre.get(name="comedy").id
    horror_id = movie2.genre.get(name="horror").id

    resp = client.get(f"/api/movies/?g={comedy_id}&g={horror_id}&dmin=1980&dmax=1990&rmin=90&rmax=150")

    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)
    assert "Even Funnier Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_avg_review(client):
    movie = MovieFactory(
        imdbid='test1234',
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
    assert resp.data["title"] == movie.title
    assert "imdb" in json.dumps(resp.data)
    assert "metacritic" in json.dumps(resp.data)
    assert resp.data["avg_rating"] == 70.0


@pytest.mark.django_db
def test_get_movies_with_avg_review(client):
    bad_movie = MovieFactory(
        imdbid='test0987',
        )
    review = Review.objects.create(
        movie=bad_movie,
        source="imdb",
        score=40
        )
    review2 = Review.objects.create(
        movie=bad_movie,
        source="metacritic",
        score=30
        )

    good_movie = MovieFactory(
        imdbid='test1234',
        )
    review = Review.objects.create(
        movie=good_movie,
        source="imdb",
        score=90
        )
    review2 = Review.objects.create(
        movie=good_movie,
        source="metacritic",
        score=86
        )

    resp = client.get(f"/api/movies/")

    
    assert resp.status_code == 200
    json_res = json.dumps(resp.data)
    json_obj = json.loads(json_res)
    assert json_obj["results"][0]["title"] == good_movie.title
    assert json_obj["results"][1]["title"] == bad_movie.title
    assert json_obj["results"][0]["avg_rating"] == 88.0
    assert json_obj["results"][1]["avg_rating"] == 35.0