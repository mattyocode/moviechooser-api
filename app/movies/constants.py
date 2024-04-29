from enum import StrEnum


class ReviewSources(StrEnum):
    """Review source string representations."""
    IMDB = "imdb"
    ROTTEN_TOMATOES = "rotten_toms"
    METACRITIC = "metacritic"

    @classmethod
    def values(cls):
        """Return list of values."""
        return list(map(str, cls))
