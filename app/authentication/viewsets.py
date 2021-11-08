from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import LoginSerializer, RegisterSerializer


class LoginViewSet(ModelViewSet, TokenObtainPairSerializer):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as err:
            raise InvalidToken(err.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RegisterViewSet(ModelViewSet, TokenObtainPairView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_data = {}
        user_data["username"] = serializer.validated_data["username"]
        user_data["email"] = serializer.validated_data["email"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": user_data,
                "refresh": str(refresh),
                "token": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )


class RefreshViewSet(ViewSet, TokenRefreshView):
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as err:
            raise InvalidToken(err.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
