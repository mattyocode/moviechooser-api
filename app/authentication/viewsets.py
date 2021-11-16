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
from .utils import recaptcha_submit


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

        is_valid_recaptcha = recaptcha_submit(
            serializer.validated_data["recaptcha_key"]
        )

        print("is_valid_recaptcha response ", is_valid_recaptcha)
        if is_valid_recaptcha is True:
            user_data = {}
            user_data["email"] = serializer.validated_data["email"]

            try:
                username = serializer.validated_data["username"]
                user_data["username"] = username
            except KeyError:
                pass

            user = serializer.save()
            user_data["uid"] = str(user.uid)
            user_data["is_active"] = user.is_active

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "user": user_data,
                    "refresh": str(refresh),
                    "token": str(refresh.access_token),
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                data={"error": "ReCAPTCHA not verified."},
                status=status.HTTP_406_NOT_ACCEPTABLE,
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
