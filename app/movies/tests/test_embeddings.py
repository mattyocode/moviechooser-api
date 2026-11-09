import subprocess
import sys
import threading
import time

import numpy as np
import pytest

from movies import embeddings

from .factories import MovieWithGenreFactory


def words(n, word="word"):
    return " ".join([word] * n)


def test_chunks_respect_word_limit_and_keep_all_words():
    text = "\n".join(f"{words(37)}. {words(52)}!" for _ in range(10))

    chunks = embeddings.chunk_text(text)

    assert len(chunks) > 1
    assert all(len(chunk.split()) <= 200 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


def test_chunks_keep_sentences_whole():
    first, second = f"{words(150, 'a')}.", f"{words(100, 'b')}."

    chunks = embeddings.chunk_text(f"{first} {second}")

    assert chunks == [first, second]


def test_long_sentence_is_split_at_word_limit():
    chunks = embeddings.chunk_text(words(450))

    assert [len(c.split()) for c in chunks] == [200, 200, 50]


def test_empty_text_has_no_chunks():
    assert embeddings.chunk_text("  \n ") == []


def test_pool_returns_unit_vector():
    pooled = embeddings.pool([[3.0, 0.0], [0.0, 10.0]])

    assert np.isclose(np.linalg.norm(pooled), 1.0)
    assert np.allclose(pooled, [np.sqrt(0.5), np.sqrt(0.5)])


def test_pool_of_one_chunk_keeps_its_direction():
    pooled = embeddings.pool([[2.0, 4.0, 4.0]])

    assert np.allclose(pooled, [1 / 3, 2 / 3, 2 / 3])


def test_embed_documents_pools_per_document():
    vectors = embeddings.embed_documents([words(450), "One short plot."])

    assert len(vectors) == 2
    assert all(v.shape == (embeddings.DIMENSIONS,) for v in vectors)
    assert all(np.isclose(np.linalg.norm(v), 1.0) for v in vectors)


def test_embed_documents_rejects_empty_text():
    with pytest.raises(ValueError):
        embeddings.embed_documents(["A plot.", ""])


def test_text_hash_is_stable_sha256():
    assert embeddings.text_hash("plot") == embeddings.text_hash("plot")
    assert len(embeddings.text_hash("plot")) == 64


def test_import_does_not_load_fastembed():
    code = "import sys, movies.embeddings; assert 'fastembed' not in sys.modules"

    subprocess.run([sys.executable, "-c", code], check=True)


def test_tests_use_fake_model_not_fastembed():
    embeddings.embed_documents(["A plot."])

    assert type(embeddings.get_model()).__name__ == "FakeEmbeddingModel"
    assert "fastembed" not in sys.modules


@pytest.mark.django_db
def test_premise_text_sorts_genres_before_plot():
    movie = MovieWithGenreFactory(
        genre=["Thriller", "Action", "Crime"], plot="A getaway driver plans a heist."
    )

    assert (
        embeddings.premise_text(movie)
        == "Action, Crime, Thriller. A getaway driver plans a heist."
    )


@pytest.mark.django_db
def test_premise_text_never_includes_title():
    movie = MovieWithGenreFactory(
        title="Driver", genre=["Action"], plot="A man drives cars for money."
    )

    assert "Driver" not in embeddings.premise_text(movie)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "genres, plot, expected",
    [
        ([], "  A plot only.  ", "A plot only."),
        (["Drama", "Comedy"], None, "Comedy, Drama"),
        (["Drama"], "   ", "Drama"),
        ([], None, ""),
        ([], "", ""),
    ],
)
def test_premise_text_with_missing_parts(genres, plot, expected):
    movie = MovieWithGenreFactory(genre=genres, plot=plot)

    assert embeddings.premise_text(movie) == expected


def test_embed_query_returns_unit_vector():
    vector = embeddings.embed_query("a getaway driver")

    assert vector.shape == (embeddings.DIMENSIONS,)
    assert np.isclose(np.linalg.norm(vector), 1.0)


def test_embed_query_normalises_text_and_caches():
    first = embeddings.embed_query(" I'm  HUNGRY ")
    second = embeddings.embed_query("i'm hungry")

    assert first is second
    assert embeddings.get_model().query_calls == ["i'm hungry"]


def test_embed_query_uses_query_embed_not_embed():
    embeddings.embed_query("heist")

    assert embeddings.get_model().query_calls == ["heist"]


def test_embed_query_vectors_are_read_only():
    vector = embeddings.embed_query("heist")

    with pytest.raises(ValueError):
        vector[0] = 1.0


def test_concurrent_first_calls_load_the_model_once(monkeypatch):
    loads = []
    start = threading.Barrier(4)

    def slow_load():
        loads.append(1)
        time.sleep(0.05)
        return object()

    monkeypatch.setattr(embeddings, "_load_model", slow_load)

    def first_call():
        start.wait()
        embeddings.get_model()

    threads = [threading.Thread(target=first_call) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert loads == [1]
