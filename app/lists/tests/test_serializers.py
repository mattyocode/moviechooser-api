import datetime

import pytest
from rest_framework import serializers

from accounts.models import CustomUser
from lists.models import List
from lists.serializers import ItemSerializer, ListSerializer
from movies.tests.factories import MovieFactory


@pytest.mark.django_db
def test_valid_list_serializer():
    user = CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    valid_serializer_data = {
        "owner": user.id,
        "name": "test list",
    }
    serializer = ListSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data["owner"] == user
    assert serializer.validated_data["name"] == "test list"
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}


def test_invalid_list_serializer():
    invalid_serializer_data = {
        "name": "test list",
    }
    serializer = ListSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {
        "owner": ["This field is required."],
    }


@pytest.mark.django_db
def test_valid_item_serializer():
    movie = MovieFactory(
        imdbid="test0987",
        title="Tester",
    )
    user = CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    _list = List.objects.create(
        owner=user,
        name="test list"
    )
    valid_serializer_data = {
        "movie": movie.imdbid,
        "_list": _list.id,
        "watched": False,
    }
    serializer = ItemSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data["movie"] == movie
    assert serializer.validated_data["_list"] == _list
    assert serializer.validated_data["watched"] is False
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}