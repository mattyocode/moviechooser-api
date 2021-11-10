from rest_framework import serializers

from accounts.models import CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["uid", "username", "email", "is_active", "date_joined", "last_login"]
        read_only_field = ["uid", "is_active", "date_joined", "last_login"]
        write_only_field = ["password"]


class UserSnippetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["uid", "username", "email", "is_active"]
