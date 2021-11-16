from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings

from accounts.models import CustomUser
from accounts.serializers import UserSerializer, UserSnippetSerializer


class RegisterSerializer(UserSerializer):
    password = serializers.CharField(
        max_length=128, min_length=8, write_only=True, required=True
    )
    recaptcha_key = serializers.CharField(required=True)

    class Meta:
        model = CustomUser
        fields = ["uid", "username", "email", "password", "recaptcha_key", "is_active"]

    def create(self, validated_data):
        if "username" not in validated_data:
            validated_data["username"] = None
        if "recaptcha_key" in validated_data:
            del validated_data["recaptcha_key"]
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


class ResetPasswordEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=500)
    redirect_url = serializers.CharField(max_length=1000, required=False)

    class Meta:
        fields = ["email"]
