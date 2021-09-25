import json

import pytest

from movies.models import Movie


@pytest.mark.django_db
def test_get_single_movie(client):
    movie = Movie.objects.create(
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
    resp = client.get(f"/api/movies/{movie.id}/")
    assert resp.status_code == 200
    assert resp.data["title"] == "Tester: Revenge of the Test"


def test_get_single_movie_incorrect_id(client):
    resp = client.get("/api/movies/foo/")
    assert resp.status_code == 404