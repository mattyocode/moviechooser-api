import datetime

import pytest
from rest_framework import serializers

from accounts.serializers import UserSerializer

@pytest.mark.django_db
def test_valid_user_serializer():
    created_date = datetime.datetime(2021, 1, 14, 0, 0, tzinfo=datetime.timezone.utc)
    updated_date = datetime.datetime(2021, 2, 15, 0, 0, tzinfo=datetime.timezone.utc)
    valid_serializer_data = {
        "username": "user1",
        "email": "standard@user.com",
        "is_active": True,
        "date_joined": created_date,
        "last_login": updated_date,
    }
    serializer = UserSerializer(data=valid_serializer_data)
    assert serializer.is_valid()
    assert serializer.validated_data == valid_serializer_data

    valid_serializer_data["date_joined"] = '2021-01-14T00:00:00Z'
    valid_serializer_data["last_login"] = '2021-02-15T00:00:00Z'
    assert serializer.data == valid_serializer_data
    assert serializer.errors == {}