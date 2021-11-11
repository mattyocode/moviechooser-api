import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser

User = CustomUser


@pytest.fixture
def refresh_client():
    user = User.objects.create_user(
        username="user1", email="standard@user.com", password="testpw1234"
    )
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")

    return client
