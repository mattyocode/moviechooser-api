import random
import time

from celery import Task, chain
from config.celery import app

from .utils import OMDBFetch

# from celery.utils.log import get_task_logger


# logger = get_task_logger(__name__)


class DelayedTask(Task):
    """Include a 1-2 second delay between requests to prevent rate limiting."""

    def run(self, *args, **kwargs):
        time.sleep(random.randint(1, 2))
        return super().run(*args, **kwargs)


@app.task(base=DelayedTask)
def fetch_movies(imdbid):
    omdb_data = OMDBFetch(imdbid).get_data()

    # logger.info("*** Catching pokemon!!! ***")
    # crawler = Crawler(logger)
    # crawler.get_all_pokemon()
    # logger.info("*** Finished catching pokemon!!! ***")
    pass
