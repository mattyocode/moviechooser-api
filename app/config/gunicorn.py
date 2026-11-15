"""Gunicorn settings for prod: warm the embedding model in each worker."""

import time


def post_worker_init(worker):
    # Load the model before the worker takes requests, so the first text search
    # doesn't wait for it. A failure is logged, not raised: the worker still
    # serves everything else, and a text search then retries the load.
    from movies import embeddings

    started = time.monotonic()
    try:
        embeddings.get_model()
    except Exception:
        worker.log.exception("Embedding model failed to load at worker boot")
    else:
        worker.log.info("Embedding model loaded in %.1fs", time.monotonic() - started)
