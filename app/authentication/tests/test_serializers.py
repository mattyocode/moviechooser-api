import json

import pytest

from accounts.models import CustomUser
from authentication.serializers import (
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordEmailSerializer,
)

User = CustomUser


@pytest.mark.django_db
def test_valid_register_serializer():
    valid_serializer_data = {
        "username": "user1",
        "email": "standard@user.com",
        "password": "testpw1234",
        "recaptcha_key": "testkey12341234",
    }
    serializer = RegisterSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    serializer.save()
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_register_serializer():
    invalid_serializer_data = {
        "username": "user1",
        "password": "testpw1234",
        "recaptcha_key": "testkey12341234",
    }
    serializer = RegisterSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    del invalid_serializer_data["recaptcha_key"]
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


@pytest.mark.django_db
def test_cant_register_existing_email():
    User.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )

    invalid_serializer_data = {
        "username": "user2",
        "email": "standard@user.com",
        "password": "testpw1234",
        "recaptcha_key": "testkey12341234",
    }
    serializer = RegisterSerializer(data=invalid_serializer_data)

    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {"email": ["Email already registered."]}


@pytest.mark.django_db
def test_cant_register_existing_username():
    User.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )

    invalid_serializer_data = {
        "username": "user1",
        "email": "other@user.com",
        "password": "testpw1234",
        "recaptcha_key": "testkey12341234",
    }
    serializer = RegisterSerializer(data=invalid_serializer_data)

    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {"username": ["Username already exists."]}


@pytest.mark.django_db
def test_valid_password_reset_serializer():
    valid_serializer_data = {
        "email": "standard@user.com",
    }
    serializer = ResetPasswordEmailSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_password_reset_serializer():
    invalid_serializer_data = {}
    serializer = ResetPasswordEmailSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {"email": ["This field is required."]}
