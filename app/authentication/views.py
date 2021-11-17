from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.urls import reverse
# from django.utils.encoding import smart_str, force_str, smart_bytes, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode  # urlsafe_base64_encode
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from accounts.models import CustomUser

from .serializers import ResetPasswordEmailSerializer


class RequestPasswordResetEmail(GenericAPIView):
    serializer_class = ResetPasswordEmailSerializer

    def post(self, request):
        # serializer = self.serializer_class(data=request.data)
        email = request.data.get("email", None)

        if CustomUser.objects.filter(email=email).exists():
            user = CustomUser.objects.get(email=email)
            uidb64 = urlsafe_base64_decode(str(user.uid))
            token = PasswordResetTokenGenerator().make_token(user)
            current_site = get_current_site(request=request).domain
            relative_link = reverse(
                "password-reset-confirm", kwargs={"uidb64": uidb64, "token": token}
            )
            redirect_url = request.data.get("redirect_url", "")
            abs_url = "https://" + current_site + relative_link

            email_body = (
                f"Hi movie fan, \n Use the following link to reset your password: \n \
                    {abs_url}?redirect_url={redirect_url}"
            )

            send_mail(
                "Reset your password",
                email_body,
                "noreply@moviechooser.co.uk",
                [user.email],
            )
        return Response(
            {"success": "Reset password email sent if account exists"},
            status=status.HTTP_200_OK,
        )


class PasswordTokenCheckAPI(GenericAPIView):
    pass
