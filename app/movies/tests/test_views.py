import datetime
import json
from unittest import mock

import pytest
from accounts.models import CustomUser
from lists.models import Item, List
from movies.models import Actor, Director, OnDemand

from .factories import MovieFactory, MovieWithGenreFactory

DEFAULT_LIST = "watch-list"


@pytest.mark.django_db
def test_get_single_movie(client):
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    resp = client.get(f"/api/movies/{movie.slug}/", follow=False)
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "-tester" in resp.data["slug"]


@pytest.mark.django_db
def test_get_single_movie_incorrect_id(client):
    resp = client.get("/api/movies/foo/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_get_random_movie(client, add_movie):
    MovieFactory(
        title="Tester",
    )
    movie_two = MovieFactory(
        title="Test 2: Revenge of the Test",
    )
    with mock.patch("random.choice", return_value=movie_two):
        resp = client.get("/api/movies/random/")
        assert resp.status_code == 200
        assert "Revenge" in json.dumps(resp.data)
        assert "Tester" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_all_movies(client, add_movie):
    movie_one = MovieFactory(
        title="Tester",
    )
    movie_two = MovieFactory(
        title="Test 2: Revenge of the Test",
    )
    resp = client.get("/api/movies/")
    assert resp.status_code == 200
    assert movie_one.title in json.dumps(resp.data)
    assert movie_two.title in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_genre(client, add_movie):
    movie = MovieWithGenreFactory(title="Tester", genre=["Comedy"])
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Comedy" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_actor(client, add_movie):
    movie = MovieFactory(
        title="Tester",
    )
    movie.actors.add(Actor.objects.create(name="Clem Fandango"))
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Clem Fandango" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_director(client, add_movie):
    movie = MovieWithGenreFactory(title="Tester", genre=["Comedy"])
    director = Director.objects.create(name="Len Z")
    movie.director.add(director)
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Len Z" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_ondemand(client, add_movie):
    movie = MovieWithGenreFactory(title="Tester", genre=["Comedy"])
    OnDemand.objects.create(movie=movie, service="Google Play", url="googleplay.com/")
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "Google Play" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_review(client, add_movie):
    movie = MovieWithGenreFactory(title="Tester", genre=["Comedy"], review=[65, 75])
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester"
    assert "_review" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_genre(client):
    movie1 = MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"])
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"])

    comedy_id = movie1.genre.get(name="comedy").id

    resp = client.get(f"/api/movies/?g={comedy_id}")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_2_genres(client):
    movie1 = MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"])
    movie2 = MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"])
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"])

    comedy_id = movie1.genre.get(name="comedy").id
    horror_id = movie2.genre.get(name="horror").id

    resp = client.get(f"/api/movies/?g={comedy_id},{horror_id}")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_single_decade(client):
    MovieWithGenreFactory.create(
        title="Funny Tests", genre=["comedy"], released=datetime.date(1990, 1, 1)
    )
    MovieWithGenreFactory.create(
        title="Scary Tests", genre=["horror"], released=datetime.date(1989, 12, 31)
    )

    resp = client.get("/api/movies/?dmin=1990&dmax=1990")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_pre_1960s_only(client):
    MovieWithGenreFactory.create(
        title="Old Movie", genre=["comedy"], released=datetime.date(1940, 1, 1)
    )
    MovieWithGenreFactory.create(
        title="New Movie", genre=["horror"], released=datetime.date(1961, 12, 31)
    )

    resp = client.get("/api/movies/?dmin=pre&dmax=pre")
    assert resp.status_code == 200
    assert "Old Movie" in json.dumps(resp.data)
    assert "New Movie" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_pre_1960s_with_numeric_decade(client):
    MovieWithGenreFactory.create(
        title="Old Movie", genre=["comedy"], released=datetime.date(1940, 1, 1)
    )
    MovieWithGenreFactory.create(
        title="New Movie", genre=["horror"], released=datetime.date(1961, 12, 31)
    )

    resp = client.get("/api/movies/?dmin=pre&dmax=1960")
    assert resp.status_code == 200
    assert "Old Movie" in json.dumps(resp.data)
    assert "New Movie" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_current_only(client):
    MovieWithGenreFactory.create(
        title="Old Movie", genre=["comedy"], released=datetime.date(1940, 1, 1)
    )
    MovieWithGenreFactory.create(
        title="New Movie", genre=["horror"], released=datetime.date(2021, 1, 31)
    )

    resp = client.get("/api/movies/?dmin=2020&dmax=2020")
    assert resp.status_code == 200
    assert "Old Movie" not in json.dumps(resp.data)
    assert "New Movie" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_release_decade_range(client):
    MovieWithGenreFactory.create(
        title="Funny Tests", genre=["comedy"], released=datetime.date(1990, 1, 1)
    )
    MovieWithGenreFactory.create(
        title="Scary Tests", genre=["horror"], released=datetime.date(1985, 12, 31)
    )
    MovieWithGenreFactory.create(
        title="Tense Tests", genre=["thriller"], released=datetime.date(2000, 1, 1)
    )

    resp = client.get("/api/movies/?dmin=1980&dmax=1990")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_single_runtime(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=90)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=120)

    resp = client.get("/api/movies/?rmin=90&rmax=90")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_single_runtime_is_fuzzy(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=93)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=94)

    resp = client.get("/api/movies/?rmin=90&rmax=90")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=90)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=120)
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"], runtime=150)

    resp = client.get("/api/movies/?rmin=90&rmax=120")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range_incl_lt(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=25)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=120)
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"], runtime=150)

    resp = client.get("/api/movies/?rmin=<75&rmax=120")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range_both_lt(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=25)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=74)
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"], runtime=75)

    resp = client.get("/api/movies/?rmin=<75&rmax=<75")
    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range_incl_gt(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=120)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=150)
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"], runtime=240)

    resp = client.get("/api/movies/?rmin=150&rmax=>150")
    assert resp.status_code == 200
    assert "Funny Tests" not in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_runtime_range_both_gt(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=150)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=151)
    MovieWithGenreFactory.create(title="Tense Tests", genre=["thriller"], runtime=200)

    resp = client.get("/api/movies/?rmin=>150&rmax=>150")
    assert resp.status_code == 200
    assert "Funny Tests" not in json.dumps(resp.data)
    assert "Scary Tests" in json.dumps(resp.data)
    assert "Tense Tests" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_queryset_filtered_by_all_criteria(client):
    movie1 = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        released=datetime.date(1985, 1, 1),
        runtime=90,
    )
    movie2 = MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        released=datetime.date(2000, 1, 1),
        runtime=120,
    )
    MovieWithGenreFactory.create(
        title="Tense Tests",
        genre=["thriller"],
        released=datetime.date(1990, 1, 1),
        runtime=150,
    )
    MovieWithGenreFactory.create(
        title="Even Funnier Tests",
        genre=["comedy"],
        released=datetime.date(1990, 1, 1),
        runtime=155,
    )

    comedy_id = movie1.genre.get(name="comedy").id
    horror_id = movie2.genre.get(name="horror").id

    resp = client.get(
        f"/api/movies/?g={comedy_id},{horror_id}&dmin=1980&dmax=1990&rmin=90&rmax=150"
    )

    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)
    assert "Tense Tests" not in json.dumps(resp.data)
    assert "Even Funnier Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_movie_with_avg_review(client):
    movie = MovieFactory(imdbid="test1234", review=[65, 75])
    resp = client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == movie.title
    assert "review" in json.dumps(resp.data)
    assert resp.data["avg_rating"] == 70.0


@pytest.mark.django_db
def test_get_movies_with_avg_review(client):
    bad_movie = MovieFactory(imdbid="test0987", review=[40, 44])

    good_movie = MovieFactory(imdbid="test1234", review=[90, 86])

    resp = client.get("/api/movies/")

    assert resp.status_code == 200
    json_res = json.dumps(resp.data)
    json_obj = json.loads(json_res)
    assert json_obj["results"][0]["title"] == good_movie.title
    assert json_obj["results"][1]["title"] == bad_movie.title
    assert json_obj["results"][0]["avg_rating"] == 88.0
    assert json_obj["results"][1]["avg_rating"] == 42.0


@pytest.mark.django_db
def test_get_genre_queryset_filtered_by_number_of_movies(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=90)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=120)
    MovieWithGenreFactory.create(title="Funny 2 Tests", genre=["comedy"], runtime=150)

    resp = client.get("/api/genres/")

    assert resp.status_code == 200
    assert "comedy" in json.dumps(resp.data[0])
    assert "horror" in json.dumps(resp.data[1])


@pytest.mark.django_db
def test_get_genre_queryset_filtered_by_number_of_movies_most_entries_first(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], runtime=90)
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], runtime=120)
    MovieWithGenreFactory.create(
        title="Thrilling Tests", genre=["thriller"], runtime=150
    )
    MovieWithGenreFactory.create(title="Funny 2 Tests", genre=["comedy"], runtime=150)
    MovieWithGenreFactory.create(title="Funny 3 Tests", genre=["comedy"], runtime=90)
    MovieWithGenreFactory.create(title="Scary 2 Tests", genre=["horror"], runtime=120)

    resp = client.get("/api/genres/")

    assert resp.status_code == 200
    assert "comedy" in json.dumps(resp.data[0])
    assert "horror" in json.dumps(resp.data[1])
    assert "thriller" in json.dumps(resp.data[2])


@pytest.mark.django_db
def test_get_queryset_single_movie_returned_if_duplicates(client):
    movie1 = MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"])
    movie1.save()

    resp = client.get("/api/movies/")
    assert resp.status_code == 200
    print(json.dumps(resp.data))
    assert '"count": 1' in json.dumps(resp.data)


@pytest.mark.django_db
def test_dont_return_movies_with_avg_score_below_40(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], review=[41])
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], review=[39])

    resp = client.get("/api/movies/")

    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_dont_return_movies_with_no_avg_score(client):
    MovieWithGenreFactory.create(title="Funny Tests", genre=["comedy"], review=[41])
    MovieWithGenreFactory.create(title="Scary Tests", genre=["horror"], review=[-1])

    resp = client.get("/api/movies/")

    assert resp.status_code == 200
    assert "Funny Tests" in json.dumps(resp.data)
    assert "Scary Tests" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_dont_return_movies_with_no_poster_url(client):
    MovieFactory.create(title="No image movie", poster_url="N/A")
    MovieFactory.create(
        title="Image movie",
    )

    resp = client.get("/api/movies/")

    assert resp.status_code == 200
    assert "Image movie" in json.dumps(resp.data)
    assert "No image movie" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_return_on_list_field_if_user_authed_and_movie_on_their_list(auth_user_client):
    user = CustomUser.objects.get(email="fixture@user.com")
    funny_movie = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        review=[90],
    )
    MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        review=[100],
    )
    MovieWithGenreFactory.create(
        title="Tense Tests",
        genre=["thriller"],
        review=[95],
    )
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(
        _list=_list,
        movie=funny_movie,
    )

    resp = auth_user_client.get("/api/movies/")

    assert resp.status_code == 200
    assert resp.data["results"][0]["title"] == "Scary Tests"
    assert resp.data["results"][0]["on_list"] is False
    assert resp.data["results"][1]["title"] == "Tense Tests"
    assert resp.data["results"][1]["on_list"] is False
    assert resp.data["results"][2]["title"] == "Funny Tests"
    assert resp.data["results"][2]["on_list"] is True


@pytest.mark.django_db
def test_return_not_on_list_if_user_not_authed(client):
    user = CustomUser.objects.create(email="standard@user.com", password="test1234")
    funny_movie = MovieWithGenreFactory.create(
        title="Funny Tests",
        genre=["comedy"],
        review=[90],
    )
    MovieWithGenreFactory.create(
        title="Scary Tests",
        genre=["horror"],
        review=[100],
    )
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(
        _list=_list,
        movie=funny_movie,
    )

    resp = client.get("/api/movies/")

    assert resp.status_code == 200
    assert resp.data["results"][0]["title"] == "Scary Tests"
    assert resp.data["results"][0]["on_list"] is False
    assert resp.data["results"][1]["title"] == "Funny Tests"
    assert resp.data["results"][1]["on_list"] is False


@pytest.mark.django_db
def test_get_single_movie_with_on_list(auth_user_client):
    user = CustomUser.objects.get(email="fixture@user.com")
    movie = MovieFactory(imdbid="test1234", review=[65, 75])
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = auth_user_client.get(f"/api/movies/{movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == movie.title
    assert resp.data["on_list"] is True


@pytest.mark.django_db
def test_get_single_movie_not_on_list(auth_user_client):
    user = CustomUser.objects.get(email="fixture@user.com")
    movie = MovieFactory(imdbid="test1234", review=[65, 75])
    other_movie = MovieFactory(imdbid="test2222", review=[100])
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = auth_user_client.get(f"/api/movies/{other_movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == other_movie.title
    assert resp.data["on_list"] is False


@pytest.mark.django_db
def test_get_single_movie_not_authed(client):
    user = CustomUser.objects.create(email="standard@user.com", password="test1234")
    movie = MovieFactory(imdbid="test1234", review=[65, 75])
    other_movie = MovieFactory(imdbid="test2222", review=[100])
    _list = List.objects.create(owner=user, name=DEFAULT_LIST)
    Item.objects.create(
        _list=_list,
        movie=movie,
    )
    resp = client.get(f"/api/movies/{other_movie.slug}/")
    assert resp.status_code == 200
    assert resp.data["title"] == other_movie.title
    assert resp.data["on_list"] is False
