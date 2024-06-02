from enum import StrEnum


class ReviewSources(StrEnum):
    """Review source string representations."""

    IMDB = "imdb"
    ROTTEN_TOMATOES = "rotten_toms"
    METACRITIC = "metacritic"

    @classmethod
    def choices(cls):
        """Return list of values and names."""
        return [(item.value, item.name) for item in cls]
