from django.contrib.auth.models import update_last_login
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import fields
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings

from accounts.models import CustomUser
from accounts.serializers import UserSerializer, UserSnippetSerializer


class RegisterSerializer(UserSerializer):
    password = serializers.CharField(
        max_length=128, min_length=8, write_only=True, required=True
    )
    username = serializers.CharField(
        max_length=24, min_length=2, write_only=True, required=True
    )
    email = serializers.EmailField(required=True, write_only=True, max_length=128)

    class Meta:
        model = CustomUser
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        try:
            user = CustomUser.objects.get(email=validated_data["email"])
        except ObjectDoesNotExist:
            try:
                user = CustomUser.objects.get(username=validated_data["username"])
            except ObjectDoesNotExist:
                user = CustomUser.objects.create_user(**validated_data)
        return user


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        refresh = self.get_token(self.user)

        data["user"] = UserSnippetSerializer(self.user).data
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data
