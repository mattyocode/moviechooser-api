import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser


@pytest.fixture
def auth_user_client():
    user = CustomUser.objects.create_user(
        username="fixtureguy", email="fixture@user.com", password="testpw"
    )
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")
    print("conftest >>>", refresh)
    return client


@pytest.fixture
def auth_superuser_client():
    user = CustomUser.objects.create_superuser(
        username="admin1", email="admin@user.com", password="admintestpw"
    )
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")
    print("conftest >>>", refresh)
    return client
