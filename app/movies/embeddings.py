"""Plot and query embeddings with fastembed.

The model loads lazily: management commands and tests load it on first use, and
gunicorn workers load it at boot (config/gunicorn.py) so text search is warm.
"""

import functools
import hashlib
import os
import re
import threading

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
CHUNK_WORDS = 200

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

_model = None
_model_lock = threading.Lock()


def _load_model():
    # Imported here: fastembed pulls in onnxruntime, which most web requests don't need.
    from fastembed import TextEmbedding

    return TextEmbedding(
        MODEL_NAME, cache_dir=os.environ.get("FASTEMBED_CACHE_PATH"), threads=1
    )


def get_model():
    global _model
    if _model is None:
        # A worker's threads can race to the first load; only one should load.
        with _model_lock:
            if _model is None:
                _model = _load_model()
    return _model


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def premise_text(movie) -> str:
    """Sorted genre names, then the OMDb short plot.

    Never the title: title words match unrelated movies (Baby Driver -> Babyteeth).
    Returns "" when the movie has neither genres nor a plot.
    """
    genres = ", ".join(sorted(genre.name for genre in movie.genre.all()))
    plot = (movie.plot or "").strip()
    if genres and plot:
        return f"{genres}. {plot}"
    return genres or plot


def split_sentences(text: str) -> list[str]:
    sentences = []
    for paragraph in text.split("\n"):
        sentences.extend(s for s in SENTENCE_END.split(paragraph.strip()) if s)
    return sentences


def chunk_text(text: str, max_words: int = CHUNK_WORDS) -> list[str]:
    """Pack whole sentences into chunks of at most max_words words.

    A sentence longer than max_words is split at word boundaries.
    """
    chunks, current = [], []
    for sentence in split_sentences(text):
        words = sentence.split()
        if len(current) + len(words) > max_words and current:
            chunks.append(" ".join(current))
            current = []
        while len(words) > max_words:
            chunks.append(" ".join(words[:max_words]))
            words = words[max_words:]
        current.extend(words)
    if current:
        chunks.append(" ".join(current))
    return chunks


def pool(vectors) -> np.ndarray:
    """Mean of the L2-normalised vectors, normalised again."""
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    mean = matrix.mean(axis=0)
    return mean / np.linalg.norm(mean)


def embed_documents(texts: list[str], batch_size: int = 16) -> list[np.ndarray]:
    """Embed each text as the pooled vector of its chunks."""
    chunked = [chunk_text(text) for text in texts]
    if any(not chunks for chunks in chunked):
        raise ValueError("Cannot embed empty text.")

    flat = [chunk for chunks in chunked for chunk in chunks]
    vectors = list(get_model().embed(flat, batch_size=batch_size))

    pooled, start = [], 0
    for chunks in chunked:
        pooled.append(pool(vectors[start : start + len(chunks)]))
        start += len(chunks)
    return pooled


def embed_query(text: str) -> np.ndarray:
    """Embed a search query, cached on its normalised text.

    Lowercases and collapses whitespace so "I'm  hungry" and "i'm hungry" share
    an entry. The cached array is read-only, since callers share it.
    """
    return _embed_normalised_query(" ".join(text.lower().split()))


@functools.lru_cache(maxsize=512)
def _embed_normalised_query(text: str) -> np.ndarray:
    # query_embed adds bge's retrieval instruction, suited to short queries
    # matched against longer passages.
    vector = next(iter(get_model().query_embed([text])))
    vector = np.asarray(vector, dtype=np.float32)
    vector.setflags(write=False)
    return vector


def clear_query_cache():
    _embed_normalised_query.cache_clear()
