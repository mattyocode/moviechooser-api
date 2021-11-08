import json

import pytest
from django.contrib.auth import get_user_model

from authentication.serializers import LoginSerializer, RegisterSerializer

User = get_user_model()


@pytest.mark.django_db
def test_valid_register_serializer():
    valid_serializer_data = {
        "username": "user1",
        "email": "standard@user.com",
        "password": "testpw1234",
    }
    serializer = RegisterSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    serializer.save()
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_register_serializer():
    invalid_serializer_data = {"username": "user1", "password": "testpw1234"}
    serializer = RegisterSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {"email": ["This field is required."]}


@pytest.mark.django_db
def test_valid_login_serializer():
    User.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    valid_serializer_data = {"email": "standard@user.com", "password": "testpw1234"}
    serializer = LoginSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert "user" in serializer.validated_data.keys()
    assert "refresh" in serializer.validated_data.keys()
    assert "access" in serializer.validated_data.keys()
    assert "standard@user.com" in serializer.validated_data["user"]["email"]
    assert "testpw1234" not in json.dumps(serializer.validated_data)
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_login_serializer():
    User.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    invalid_serializer_data = {
        "username": "standard@user.com",
        "password": "testpw1234",
    }
    serializer = LoginSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == {"password": "testpw1234"}
    assert serializer.errors == {"email": ["This field is required."]}
