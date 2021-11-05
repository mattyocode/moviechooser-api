import json

import pytest

from accounts.models import CustomUser


@pytest.mark.django_db
def test_get_all_users_if_superuser(auth_superuser_client):
    CustomUser.objects.create_user(
        username="user1", 
        email="standard@user.com", 
        password="testpw"
    )
    resp = auth_superuser_client.get(f"/auth/user/")
    assert resp.status_code == 200
    assert "user1" in json.dumps(resp.data)
    # Inlcudes user and superuser created in fixture
    assert len(resp.data["results"]) == 2


@pytest.mark.django_db
def test_not_get_all_users_if_standard_user(auth_user_client):
    CustomUser.objects.create_user(
        username="user1", 
        email="standard@user.com", 
        password="testpw"
    )
    resp = auth_user_client.get(f"/auth/user/")
    assert resp.status_code == 403
    assert "user1" not in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_all_users_fails_if_post_request(auth_superuser_client):
    CustomUser.objects.create_user(
        username="user1", 
        email="standard@user.com", 
        password="testpw"
    )
    resp = auth_superuser_client.post(f"/auth/user/")
    assert resp.status_code == 405
    assert "not allowed" in json.dumps(resp.data)


@pytest.mark.django_db
def test_get_single_user_if_superuser(auth_superuser_client):
    user = CustomUser.objects.create_user(
        username="user1", 
        email="standard@user.com", 
        password="testpw"
    )
    resp = auth_superuser_client.get(f"/auth/user/{user.id}/")
    assert resp.status_code == 200
    assert "user1" in json.dumps(resp.data)


@pytest.mark.django_db
def test_not_allowed_get_single_user_if_not_superuser(auth_user_client):
    user = CustomUser.objects.create_user(
        username="user1", 
        email="standard@user.com", 
        password="testpw"
    )
    resp = auth_user_client.get(f"/auth/user/{user.id}/")
    assert resp.status_code == 403
    assert "do not have permission" in json.dumps(resp.data)
