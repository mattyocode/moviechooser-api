import hashlib

import numpy as np
import pytest
from django.core.cache import cache
from pytest_factoryboy import register

from movies import embeddings, tmdb
from movies.models import Movie

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


class FakeEmbeddingModel:
    """Deterministic stand-in for fastembed: one unit vector per text."""

    def __init__(self):
        self.query_calls = []

    def embed(self, texts, batch_size=16):
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")
            vector = np.random.default_rng(seed).standard_normal(embeddings.DIMENSIONS)
            yield (vector / np.linalg.norm(vector)).astype(np.float32)

    def query_embed(self, texts):
        self.query_calls.extend(texts)
        yield from self.embed(texts)


class FakeTMDBClient:
    """Stand-in for movies.tmdb.TMDBClient with canned data and call counts.

    find: {imdbid: tmdb_id or None}; watch: {tmdb_id: results by country};
    regions: TMDB's regions list. Set fail to True (every call) or to a set
    of imdbids/tmdb_ids (just those) to raise TMDBError.
    """

    def __init__(self):
        self.find = {}
        self.watch = {}
        self.region_list = []
        self.fail = False
        self.calls = []

    def _maybe_fail(self, key):
        if self.fail is True or (self.fail and key in self.fail):
            raise tmdb.TMDBError(f"fake failure for {key}")

    def find_movie_id(self, imdbid):
        self.calls.append(("find", imdbid))
        self._maybe_fail(imdbid)
        return self.find.get(imdbid)

    def watch_providers(self, tmdb_id):
        self.calls.append(("watch", tmdb_id))
        self._maybe_fail(tmdb_id)
        return self.watch.get(tmdb_id, {})

    def regions(self):
        self.calls.append(("regions", None))
        self._maybe_fail("regions")
        return self.region_list

    def count(self, kind):
        return sum(1 for call_kind, _ in self.calls if call_kind == kind)


@pytest.fixture
def fake_tmdb(db, monkeypatch):
    """Every get_tmdb_client() call gets this fake, starting from an empty cache."""
    client = FakeTMDBClient()
    monkeypatch.setattr(tmdb, "get_tmdb_client", lambda: client)
    cache.clear()
    yield client
    cache.clear()


@pytest.fixture(autouse=True)
def fake_embedding_model(monkeypatch):
    """Tests never download or run the real model."""
    monkeypatch.setattr(embeddings, "_model", None)
    monkeypatch.setattr(embeddings, "_load_model", FakeEmbeddingModel)
    embeddings.clear_query_cache()
    yield
    embeddings.clear_query_cache()
