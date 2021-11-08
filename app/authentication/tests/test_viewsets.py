import json

import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser


@pytest.mark.django_db
def test_login_successfully(client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    resp = client.post(
        "/auth/login/", {"email": "standard@user.com", "password": "testpw1234"}
    )
    assert resp.status_code == 200
    assert "user" in resp.data.keys()
    assert "refresh" in resp.data.keys()
    assert "access" in resp.data.keys()
    assert "standard@user.com" in resp.data["user"]["email"]
    assert "user1" in resp.data["user"]["username"]
    assert "testpw1234" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_login_fails_with_wrong_password(client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    resp = client.post(
        "/auth/login/", {"email": "standard@user.com", "password": "testpw9999"}
    )
    assert resp.status_code == 401
    assert "No active account found" in json.dumps(resp.data)


@pytest.mark.django_db
def test_login_fails_with_wrong_email(client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    resp = client.post(
        "/auth/login/", {"email": "standard999@user.com", "password": "testpw1234"}
    )
    assert resp.status_code == 401
    assert "No active account found" in json.dumps(resp.data)


@pytest.mark.django_db
def test_register_successfully(client):
    resp = client.post(
        "/auth/register/",
        {"username": "user1", "email": "standard@user.com", "password": "testpw1234"},
    )
    assert resp.status_code == 201
    assert "user" in resp.data.keys()
    assert "token" in resp.data.keys()
    assert "refresh" in resp.data.keys()
    assert "standard@user.com" in resp.data["user"]["email"]
    assert "user1" in resp.data["user"]["username"]
    assert "testpw1234" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_register_unsuccessful_with_short_password(client):
    resp = client.post(
        "/auth/register/",
        {"username": "user1", "email": "standard@user.com", "password": "test"},
    )
    assert resp.status_code == 400
    assert "password" in resp.data.keys()
    assert "Ensure this field has at least 8 characters" in json.dumps(resp.data)


@pytest.mark.django_db
def test_register_unsuccessful_with_no_username(client):
    resp = client.post(
        "/auth/register/", {"email": "standard@user.com", "password": "test1234"}
    )
    assert resp.status_code == 400
    assert "username" in resp.data.keys()
    assert "This field is required" in json.dumps(resp.data)


@pytest.mark.django_db
def test_register_unsuccessful_with_no_email(client):
    resp = client.post("/auth/register/", {"username": "user1", "password": "test1234"})
    assert resp.status_code == 400
    assert "email" in resp.data.keys()
    assert "This field is required" in json.dumps(resp.data)


@pytest.mark.django_db
def test_refresh_token_successfully(client):
    user = CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    refresh = RefreshToken.for_user(user)
    print(refresh)
    resp = client.post("/auth/refresh/", {"refresh": f"{refresh}"})
    assert resp.status_code == 200
    assert "access" in resp.data.keys()
    assert "refresh" in resp.data.keys()


@pytest.mark.django_db
def test_refresh_token_fails_with_bad_token(client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    resp = client.post(
        "/auth/refresh/",
        {
            "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.\
                eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.\
                    SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        },
    )
    assert resp.status_code == 401
    assert "token_not_valid" in resp.data["code"]
    assert "refresh" not in resp.data.keys()