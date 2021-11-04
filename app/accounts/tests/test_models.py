from django.contrib.auth import get_user_model

import pytest


@pytest.mark.django_db
def test_create_user():
    User = get_user_model()
    user = User.objects.create_user(username="user1", email="standard@user.com", password="testpw")
    assert user.username == "user1"
    assert user.email == "standard@user.com"
    assert user.is_active == True
    assert user.is_staff == False
    assert user.is_superuser == False


@pytest.mark.django_db
def test_create_superuser():
    User = get_user_model()
    admin_user = User.objects.create_superuser(username="admin1", email="super@user.com", password="testpw")
    assert admin_user.username == "admin1"
    assert admin_user.email == "super@user.com"
    assert admin_user.is_active == True
    assert admin_user.is_staff == True
    assert admin_user.is_superuser == True
