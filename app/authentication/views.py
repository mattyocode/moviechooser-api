import os

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpResponsePermanentRedirect
from django.urls import reverse
from django.utils.encoding import smart_str, force_str, smart_bytes, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.models import CustomUser
from .serializers import ResetPasswordEmailSerializer, SetNewPasswordSerializer
from .utils import recaptcha_submit

DEBUG = os.environ.get("DEBUG", 0)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")


class CustomRedirect(HttpResponsePermanentRedirect):
    print("custom redirect")
    allowed_schemes = [os.environ.get('DEBUG'), 'https', 'http']


class RequestPasswordResetEmail(GenericAPIView):
    serializer_class = ResetPasswordEmailSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = request.data.get("email", "")
        is_valid_recaptcha = recaptcha_submit(
            serializer.validated_data["recaptcha_key"]
        )

        if CustomUser.objects.filter(email=email).exists() and is_valid_recaptcha:
            user = CustomUser.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
            token = PasswordResetTokenGenerator().make_token(user)
            current_site = get_current_site(request=request).domain
            relative_link = reverse(
                "password-reset-confirm", kwargs={"uidb64": uidb64, "token": token}
            )
            if DEBUG:
                scheme = "http://"
            else:
                scheme = "https://"
            abs_url = scheme + current_site + relative_link
            redirect_url = request.data.get("redirect_url", "")

            email_body = (
                f"Hi movie fan, \n Use the following link to reset your password: \n\
                {abs_url}?redirect_url={redirect_url}"
            )
            send_mail(
                subject="Reset your password",
                message=email_body,
                from_email="noreply@moviechooser.co.uk",
                recipient_list=[f"{user.email}"],
            )
        return Response(
            {"success": "Reset password email sent if account exists"},
            status=status.HTTP_200_OK,
        )


class PasswordTokenCheck(GenericAPIView):
    serializer_class = SetNewPasswordSerializer

    def get(self, request, uidb64, token):
        redirect_url = request.GET.get("redirect_url", "")
        print("PasswordTokenCheckAPI runs!!!", redirect_url)
        try:
            uid = smart_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(uid=uid)
            if not PasswordResetTokenGenerator().check_token(user, token):
                if redirect_url != "":
                    return CustomRedirect(
                        f"{redirect_url}/?token_valid=False"
                    )
                else:
                    return CustomRedirect(
                        f"{FRONTEND_URL}/?token_valid=False"
                    )

            if redirect_url != "":
                return CustomRedirect(
                    f"{redirect_url}/?token_valid=True&message=valid&uidb64={uidb64}&token={token}"
                )
            else:
                return CustomRedirect(
                    f"{FRONTEND_URL}/?token_valid=False"
                )

        except (DjangoUnicodeDecodeError, ObjectDoesNotExist) as err:
            pass
            
        return Response({
            "error": "Token is invalid. Please reset your password again to request a new one"
            }, status=status.HTTP_400_BAD_REQUEST)


class SetNewPassword(GenericAPIView):
    serializer_class = SetNewPasswordSerializer

    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            return Response({"success": True, "message": "Password has been reset."}, status=status.HTTP_200_OK)
        except ValidationError:
            return Response({
            "success": False,
            "message": "Password or token is invalid. Please reset your password again to request a new one"
            }, status=status.HTTP_400_BAD_REQUEST)
