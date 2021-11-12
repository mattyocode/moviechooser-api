import json

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser


@pytest.mark.django_db
def test_get_all_users_if_superuser(auth_superuser_client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw"
    )
    resp = auth_superuser_client.get("/accounts/user/")
    assert resp.status_code == 200
    assert "user1" in json.dumps(resp.data)
    # Inlcudes user and superuser created in fixture
    assert len(resp.data["results"]) == 2


@pytest.mark.django_db
def test_not_get_all_users_if_standard_user(auth_user_client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw"
    )
    resp = auth_user_client.get("/accounts/user/")
    assert resp.status_code == 403
    assert "user1" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_all_users_fails_if_post_request(auth_superuser_client):
    CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw"
    )
    resp = auth_superuser_client.post("/accounts/user/")
    assert resp.status_code == 405
    assert "not allowed" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_user_if_superuser(auth_superuser_client):
    user = CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw"
    )
    resp = auth_superuser_client.get(f"/accounts/user/{user.id}/")
    assert resp.status_code == 200
    assert "user1" in json.dumps(resp.data)


@pytest.mark.django_db
def test_user_can_only_get_own_profile():
    user1 = CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw123"
    )
    refresh = RefreshToken.for_user(user1)
    client1 = APIClient()
    client1.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")

    user2 = CustomUser.objects.create_user(
        username="user2", email="another@user.com", password="testpw123"
    )

    # user1 can't get user2's profile
    resp = client1.get(f"/accounts/user/{user2.id}/")
    assert resp.status_code == 403
    assert "do not have permission" in json.dumps(resp.data)

    # user1 can get their own profile
    refresh = RefreshToken.for_user(user1)
    client1.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")
    resp = client1.get(f"/accounts/user/{user1.id}/")
    assert resp.status_code == 200
    assert "user1" in json.dumps(resp.data)


@pytest.mark.django_db
def test_unauthorized_user_cannot_get_own_profile(client):
    user = CustomUser.objects.create_user(
        username="user1", email="standard@user.com", password="testpw"
    )
    resp = client.get(f"/accounts/user/{user.id}/")
    assert resp.status_code == 401
    assert "Authentication credentials were not provided" in json.dumps(resp.data)
