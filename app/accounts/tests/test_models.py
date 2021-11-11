import pytest

from accounts.models import CustomUser


@pytest.mark.django_db
def test_create_user():
    User = CustomUser
    user = User.objects.create_user(email="standard@user.com", password="testpw")
    assert user.username is None
    assert user.email == "standard@user.com"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_create_user_with_username():
    User = CustomUser
    user = User.objects.create_user(
        username="user1", email="standard@user.com", password="testpw"
    )
    assert user.username == "user1"
    assert user.email == "standard@user.com"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_create_superuser():
    User = CustomUser
    admin_user = User.objects.create_superuser(
        username="admin1", email="super@user.com", password="testpw"
    )
    assert admin_user.username == "admin1"
    assert admin_user.email == "super@user.com"
    assert admin_user.is_active is True
    assert admin_user.is_staff is True
    assert admin_user.is_superuser is True
