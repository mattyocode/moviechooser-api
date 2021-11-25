import json

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import smart_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import CustomUser
from authentication.serializers import (
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordEmailSerializer,
    SetNewPasswordSerializer,
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
        "recaptcha_key": "testkey12341234",
    }
    serializer = ResetPasswordEmailSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_password_reset_serializer():
    invalid_serializer_data = {
        "recaptcha_key": "testkey12341234",
    }
    serializer = ResetPasswordEmailSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert serializer.errors == {"email": ["This field is required."]}


@pytest.mark.django_db
def test_valid_set_new_password():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    token = PasswordResetTokenGenerator().make_token(user)
    valid_serializer_data = {
        "password": "test1234",
        "uidb64": uidb64,
        "token": token,
    }
    serializer = SetNewPasswordSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == user
    assert serializer.errors == {}


@pytest.mark.django_db
def test_invalid_set_new_password_short_password():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    token = PasswordResetTokenGenerator().make_token(user)
    invalid_serializer_data = {
        "password": "test",
        "uidb64": uidb64,
        "token": token,
    }
    serializer = SetNewPasswordSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert "password" in json.dumps(serializer.errors)
    assert "Ensure this field has at least 8 characters." in json.dumps(
        serializer.errors
    )


@pytest.mark.django_db
def test_set_new_password_bad_uidb64():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    fake_user_uid = "c2cf96e3-172e-4571-bb1a-71ed0f5ce037"
    uidb64 = urlsafe_base64_encode(smart_bytes(fake_user_uid))
    token = PasswordResetTokenGenerator().make_token(user)
    invalid_serializer_data = {
        "password": "test1234",
        "uidb64": uidb64,
        "token": token,
    }
    serializer = SetNewPasswordSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert "non_field_errors" in json.dumps(serializer.errors)
    assert "Reset link is invalid" in json.dumps(serializer.errors)


@pytest.mark.django_db
def test_set_new_password_bad_token():
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    bad_token = "faketn-4a85d1ec5dcbed69570c1b9721b3acca"
    invalid_serializer_data = {
        "password": "test1234",
        "uidb64": uidb64,
        "token": bad_token,
    }
    serializer = SetNewPasswordSerializer(data=invalid_serializer_data)
    assert not serializer.is_valid()
    assert serializer.validated_data == {}
    assert serializer.data == invalid_serializer_data
    assert "non_field_errors" in json.dumps(serializer.errors)
    assert "Reset link is invalid" in json.dumps(serializer.errors)
