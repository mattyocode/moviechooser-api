from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from accounts.models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        max_length=24,
        min_length=2,
        required=False,
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(), message="Username already exists."
            )
        ],
    )
    email = serializers.EmailField(
        required=True,
        max_length=128,
        validators=[
            UniqueValidator(
                queryset=CustomUser.objects.all(), message="Email already registered."
            )
        ],
    )

    class Meta:
        model = CustomUser
        fields = ["uid", "username", "email", "is_active", "date_joined", "last_login"]
        read_only_field = ["uid", "is_active", "date_joined", "last_login"]
        write_only_field = ["password"]


class UserSnippetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["uid", "username", "email", "is_active"]
