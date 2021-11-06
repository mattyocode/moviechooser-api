from django.contrib.auth import get_user_model

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

@pytest.fixture
def auth_user_client():
    user = User.objects.create_user(username="fixtureguy", email="fixture@user.com", password="testpw")
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")

    return client


@pytest.fixture
def auth_superuser_client():
    user = User.objects.create_superuser(username="admin1", email="admin@user.com", password="admintestpw")
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"JWT {refresh.access_token}")

    return client