from collections import OrderedDict
import datetime

from movies.serializers import MovieSerializer

def test_valid_movie_serializer():
    released_date = datetime.date(2021, 1, 14)
    valid_serializer_data = {
        'imdbid': 'test1234',
        'title': 'Tester: Revenge of the Test',
        'rated': 'PG',
        'released': released_date,
        'runtime': 100,
        'writer': 'Check Itt', 
        'plot': 'Once upon a time...', 
        'language': 'English', 
        'country': 'UK', 
        'poster_url': 'www.example.com/image/location/img.jpg',
        'type_field': 'movie'
    }
    serializer = MovieSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data

    valid_serializer_data['released'] = '2021-01-14'
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}

def test_invalid_movie_serializer():
    invalid_serializer_data = {
        'imdbid': 'test1234',
        'title': 'Tester: Revenge of the Test',
    }
    serializer = MovieSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "poster_url": ["This field is required."],
        "released": ["This field is required."],
        "writer": ["This field is required."],
        }