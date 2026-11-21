"""Catalogue imports only create movies, so they never touch a stored poster
path (which check_posters may have repaired)."""

from movies import tasks
from movies.models import Movie

from .factories import MovieFactory

OMDB_DATA = {
    "imdbID": "tt2",
    "Title": "New Film",
    "Rated": "PG",
    "Released": "2001-01-01",
    "Runtime": 100,
    "Writer": "A Writer",
    "Plot": "A plot.",
    "Language": "English",
    "Country": "UK",
    "Poster": "https://m.media-amazon.com/images/new.jpg",
    "Actors": "An Actor",
    "Director": "A Director",
    "Genre": "Drama",
    "Ratings": {},
}


def test_import_keeps_existing_poster_path(db, monkeypatch):
    MovieFactory(imdbid="tt1", poster_path="/fixed.jpg")
    monkeypatch.setattr(tasks, "get_imdbids_from_webpage", lambda url: ["tt1", "tt2"])
    fetched = []

    class FakeFetch:
        def __init__(self, imdbid):
            fetched.append(imdbid)

        def get_data(self):
            return OMDB_DATA

    monkeypatch.setattr(tasks, "OMDBFetch", FakeFetch)
    monkeypatch.setattr(tasks.time, "sleep", lambda s: None)

    tasks.add_movies_from_url_to_db("https://example.com/list")

    assert fetched == ["tt2"]
    assert Movie.objects.get(imdbid="tt1").poster_path == "/fixed.jpg"
    new = Movie.objects.get(imdbid="tt2")
    assert new.poster_path is None
    assert new.poster_url == OMDB_DATA["Poster"]
