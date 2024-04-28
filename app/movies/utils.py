import logging
import os
import re

import requests
from django.core.exceptions import ObjectDoesNotExist
from lists.models import Item, List

log = logging.Logger(__name__)


OMDB_API_KEY = os.environ.get("OMDB_API_KEY")
OMDBID_URL = "http://www.omdbapi.com/?i={imdbid}&apikey={API_KEY}"


def annotate_object_if_auth(request, movie):
    """
    TODO: Annotate objects via queryset annotate method.
    """
    # movie.avg_rating = movie.reviews.aggregate(avg_score=Avg("score"))["avg_score"]
    movie.on_list = False

    if request.user.is_authenticated:
        try:
            _list = List.objects.get(owner=request.user)
            items = Item.objects.filter(_list=_list)
            if items.filter(movie=movie).exists():
                movie.on_list = True
        except ObjectDoesNotExist:
            pass

    return movie


class OMDBFetch:
    """Class to handle fetching movie data for adding to DB."""

    def __init__(self, imdbid: str):
        self.imdbid = imdbid

    def request_data(self, url):
        try:
            with requests.get(url) as response:
                response.raise_for_status()
                data = response.json()
                if data["Response"] == "True":
                    return data
        except requests.RequestException as e:
            log.error(f"Request failed for url {url}. Error: {e}")

    def search_by_id(self):

        url = OMDBID_URL.format(imdbid=self.imdbid, API_KEY=OMDB_API_KEY)
        data = self.request_data(url)
        return data

    def runtime_to_int(self, omdb_json):
        """Remove non-digit characters ('min') and cast to int."""
        try:
            omdb_json["Runtime"] = int(re.sub(r"\D+", "", omdb_json["Runtime"]))
        except (KeyError, ValueError):
            omdb_json["Runtime"] = None
        return omdb_json

    def format_reviews(self, omdb_json):
        formatted_reviews = []
        reviews = omdb_json["Ratings"]
        for review in reviews:
            score_extract_functions = {
                "Internet Movie Database": lambda score: int(
                    float(score[: score.find("/")]) * 10
                ),
                "Metacritic": lambda score: int(score[: score.find("/")]),
                "Rotten Tomatoes": lambda score: int(score[: score.find("%")]),
            }
            source_column_name = {
                "Internet Movie Database": "imdb",
                "Metacritic": "metacritic",
                "Rotten Tomatoes": "rotten_toms",
            }
            try:
                source_name = source_column_name[review["Source"]]
                base_score = review["Value"]
                score_extract_function = score_extract_functions[review["Source"]]
                score_integer = score_extract_function(base_score)
                formatted_reviews.append(
                    (source_name, score_integer if 0 <= score_integer <= 100 else None)
                )

            except (ValueError, KeyError) as e:
                log.error(f"Error on {omdb_json['imdbID']}, {review}: {e}\n")

        omdb_json["Ratings"] = {}
        for review in formatted_reviews:
            omdb_json["Ratings"][review[0]] = review[1]
        return omdb_json

    def add_ag_score(self, omdb_json):
        total = 0
        num_scores = 0
        if omdb_json["imdbRating"]:
            total += omdb_json["imdbRating"]
            num_scores += 1
        if omdb_json["Metascore"]:
            total += omdb_json["Metascore"]
            num_scores += 1
        if omdb_json["Rottenscore"]:
            total += omdb_json["Rottenscore"]
            num_scores += 1

        total = total / num_scores if num_scores else None

        if num_scores == 1:
            total = total * 0.95
        omdb_json["ag_score"] = round(total, 1)
        return omdb_json

    def released_to_date_format(self, omdb_json):
        try:
            if omdb_json["Released"] != "N/A":
                date_str = omdb_json["Released"]
                omdb_json["Released"] = re.sub(" ", "-", date_str)
            else:
                omdb_json["Released"] = None
        except KeyError:
            pass
        return omdb_json

    def check_keys_exist(self, omdb_json):
        required_keys = {
            "imdbID",
            "Genre",
            "Ratings",
            "Actors",
            "Director",
            "Runtime",
            "Released",
        }
        actual_keys = set(omdb_json.keys())
        missing_keys = required_keys - actual_keys
        if missing_keys:
            return False
        return True

    def check_required_values_exist(self, omdb_json):
        required_fields = ["Genre", "Director", "Plot", "Released"]
        if (any(omdb_json[field] == None for field in required_fields)) or (
            any(omdb_json[field] == "N/A" for field in required_fields)
        ):
            return False
        return True

    def format_response_data(self, omdb_json):
        omdb_json = self.runtime_to_int(omdb_json)
        omdb_json = self.format_reviews(omdb_json)
        omdb_json = self.released_to_date_format(omdb_json)
        omdb_json = self.add_ag_score(omdb_json)
        return omdb_json

    def get_data(self):
        try:
            response = self.search_by_id()
            if self.check_keys_exist(response):
                formatted_response = self.format_response_data(response)
            if self.check_required_values_exist(formatted_response):
                return formatted_response
        except (TypeError, IndexError) as e:
            log.error("Formatted data error: ", e)
