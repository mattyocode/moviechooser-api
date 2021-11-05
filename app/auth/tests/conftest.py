from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

import pytest

User = get_user_model()

@pytest.fixture
def auth_user():
    user = User.objects.create_user(username="user1", email="standard@user.com", password="testpw1234")
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")

    return user