from unittest.mock import MagicMock

import pytest
from movies.utils import OMDBFetch


@pytest.fixture
def omdb_instance():
    """Fixture returns OMDB instance."""
    omdb_instance = OMDBFetch("tt11525644")
    return omdb_instance


# def test_requests_get_called_with_id(omdb_instance, mock_requests_get):
#     omdb_instance.write_to_json = MagicMock()
#     omdb_instance.search_by_id("tt11525644")
#     args, _ = mock_requests_get.call_args
#     assert "tt11525644" in args[0]
#     omdb_instance.write_to_json.assert_called()


def test_runtime_to_int(omdb_instance):
    omdb_obj = {"Runtime": "115 min"}
    output = omdb_instance.runtime_to_int(omdb_obj)
    assert output == {"Runtime": 115}


def test_runtime_to_int_without_runtime_in_data(omdb_instance):
    output = omdb_instance.runtime_to_int({})
    assert output == {"Runtime": None}


def test_format_reviews(omdb_instance):
    omdb_obj = {
        "imdbID":"tt2582496",
        "Ratings": [
            {"Source": "Internet Movie Database", "Value": "6.5/10"},
            {"Source": "Rotten Tomatoes", "Value": "91%"},
            {"Source": "Metacritic", "Value": "76/100"},
        ]
    }
    output = omdb_instance.format_reviews(omdb_obj)
    expected_output = {
        "imdb": 65,
        "rotten_toms": 91,
        "metacritic": 76
    }
    assert output["Ratings"] == expected_output

def test_released_to_date_format(omdb_instance):
    omdb_obj = {"Released": "01 Jul 2021"}
    output = omdb_instance.released_to_date_format(omdb_obj)
    assert output == {"Released": "01-Jul-2021"}


def test_released_to_date_format_with_NA(omdb_instance):
    omdb_obj = {"Released": "N/A"}
    output = omdb_instance.released_to_date_format(omdb_obj)
    assert output == {"Released": None}


def test_check_keys_exist(omdb_instance):
    omdb_obj = {
        "imdbID": "tt11525644",
        "Genre": "Crime, Drama, Mystery",
        "Ratings": [
            {"Source": "Internet Movie Database", "Value": "6.5/10"},
            {"Source": "Rotten Tomatoes", "Value": "91%"},
            {"Source": "Metacritic", "Value": "76/100"},
        ],
        "Actors": "Don Cheadle, Benicio Del Toro, David Harbour",
        "Director": "Steven Soderbergh",
        "Runtime": "115 min",
        "Released": "01 Jul 2021",
    }
    output = omdb_instance.check_keys_exist(omdb_obj)
    assert output == True


def test_check_keys_exists_raises_KeyError(omdb_instance):
    omdb_obj = {}
    output = omdb_instance.check_keys_exist(omdb_obj)
    assert output == False


def test_check_values(omdb_instance):
    omdb_obj = {
        "Title": "No Sudden Move",
        "Released": "01 Jul 2021",
        "Genre": "Crime, Drama, Mystery",
        "Director": "Steven Soderbergh",
        "Plot": "A group of criminals are brought together...",
    }
    output = omdb_instance.check_required_values_exist(omdb_obj)
    assert output == True


def test_check_values_returns_false(omdb_instance):
    omdb_obj = {
        "Released": "N/A",
        "Genre": "N/A",
        "Director": "Steven Soderbergh",
        "Plot": "A group of criminals are brought together...",
    }
    output = omdb_instance.check_required_values_exist(omdb_obj)
    assert output == False


# Integration test
def test_json_to_postgres_format(omdb_instance):
    omdb_obj = {
        "Title": "No Sudden Move",
        "Released": "01 Jul 2021",
        "Runtime": "999 min",
        "Ratings": [
            {"Source": "Internet Movie Database", "Value": "6.5/10"},
            {"Source": "Rotten Tomatoes", "Value": "91%"},
            {"Source": "Metacritic", "Value": "76/100"},
        ],
        "Metascore": "76",
        "imdbRating": "6.5",
        "imdbID": "tt11525644",
        "Response": "True",
    }
    output = omdb_instance.json_to_postgres_format(omdb_obj)
    assert output["Runtime"] == 999
    assert output["imdbRating"] == 65
    assert output["Metascore"] == 76
    assert output["Rottenscore"] == 91
    assert output["Released"] == "01-Jul-2021"
    assert output["ag_score"] == 77.3


# Integration test
def test_data_for_postgres_by_id(omdb_instance, mock_requests_get):
    omdb_instance.write_to_json = MagicMock()
    omdb_instance.add_to_error_log = MagicMock()
    output = omdb_instance.data_for_postgres_by_id("tt11525644")
    assert output["Runtime"] == 999
    assert output["imdbRating"] == 65
    assert output["Metascore"] == 76
    assert output["Rottenscore"] == 91
    assert output["Released"] == "01-Jul-2021"
    assert output["ag_score"] == 77.3
