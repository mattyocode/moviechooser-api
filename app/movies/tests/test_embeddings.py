import subprocess
import sys

import numpy as np
import pytest

from movies import embeddings


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
