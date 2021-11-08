from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["uid", "username", "email", "is_active", "date_joined", "last_login"]
        read_only_field = ["uid", "is_active", "date_joined", "last_login"]
        write_only_field = ["password"]


class UserSnippetSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["username", "email"]
