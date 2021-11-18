import os
from unittest.mock import patch

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.test import TestCase, Client
from django.utils.encoding import smart_str, force_str, smart_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
import pytest

from accounts.models import CustomUser

FRONTEND_URL = os.environ.get("FRONTEND_URL", "")


@pytest.mark.django_db
def test_send_pw_reset_email_user_exists(client):
    CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    with patch("authentication.views.send_mail") as mock_send_mail:
        resp = client.post(
            "/auth/request-reset-email/", data={"email": "standard@user.com"}
        )
        assert resp.status_code == 200
        assert resp.data["success"] == "Reset password email sent if account exists"
        args = mock_send_mail.call_args.kwargs
        assert "Reset your password" in str(args)
        assert "standard@user.com" in args["recipient_list"][0]


@pytest.mark.django_db
def test_dont_send_pw_reset_email_user_doesnt_exist(client):
    """
    It returns success message but no email is sent.
    """
    CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    with patch("authentication.views.send_mail") as mock_send_mail:
        resp = client.post(
            "/auth/request-reset-email/", data={"email": "another@user.com"}
        )
        assert resp.status_code == 200
        assert resp.data["success"] == "Reset password email sent if account exists"
        assert mock_send_mail.call_count == 0


@pytest.mark.django_db
def test_valid_token_check_with_redirect(client):
    user = CustomUser.objects.create_user(email="standard3@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    token = PasswordResetTokenGenerator().make_token(user)
    redirect_url = "http://localhost"
    resp = client.get(
        f"/auth/password-reset-confirm/{uidb64}/{token}/?redirect_url={redirect_url}",
        follow=True
    )
    print("redirect chain", resp.redirect_chain)
    assert token in resp.redirect_chain[-1][0]
    assert uidb64 in resp.redirect_chain[-1][0]
    assert redirect_url in resp.redirect_chain[-1][0]
    assert 'token_valid=True' in resp.redirect_chain[-1][0]
    assert 301 == resp.redirect_chain[-1][1]


@pytest.mark.django_db
def test_valid_token_check_without_redirect(client):
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    token = PasswordResetTokenGenerator().make_token(user)
    redirect_url = ""
    resp = client.get(
        f"/auth/password-reset-confirm/{uidb64}/{token}/?redirect_url={redirect_url}",
        follow=True
    )
    print("redirect chain", resp.redirect_chain)
    assert token not in resp.redirect_chain[-1][0]
    assert uidb64 not in resp.redirect_chain[-1][0]
    assert FRONTEND_URL in resp.redirect_chain[-1][0]
    assert 'token_valid=False' in resp.redirect_chain[-1][0]
    assert 301 == resp.redirect_chain[-1][1]


@pytest.mark.django_db
def test_invalid_token_check_with_redirect(client):
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    bad_token = "faketn-4a85d1ec5dcbed69570c1b9721b3acca"
    redirect_url = "http://localhost"
    resp = client.get(
        f"/auth/password-reset-confirm/{uidb64}/{bad_token}/?redirect_url={redirect_url}",
        follow=True
    )
    assert uidb64 not in resp.redirect_chain[-1][0]
    assert bad_token not in resp.redirect_chain[-1][0]
    assert redirect_url in resp.redirect_chain[-1][0]
    assert 'token_valid=False' in resp.redirect_chain[-1][0]
    assert 301 == resp.redirect_chain[-1][1]


@pytest.mark.django_db
def test_invalid_token_check_without_redirect(client):
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    uidb64 = urlsafe_base64_encode(smart_bytes(user.uid))
    bad_token = "faketn-4a85d1ec5dcbed69570c1b9721b3acca"
    redirect_url = ""
    resp = client.get(
        f"/auth/password-reset-confirm/{uidb64}/{bad_token}/?redirect_url={redirect_url}",
        follow=True
    )
    assert uidb64 not in resp.redirect_chain[-1][0]
    assert bad_token not in resp.redirect_chain[-1][0]
    assert FRONTEND_URL in resp.redirect_chain[-1][0]
    assert 'token_valid=False' in resp.redirect_chain[-1][0]
    assert 301 == resp.redirect_chain[-1][1]


@pytest.mark.django_db
def test_invalid_user_uidb64_returns_400_error(client):
    user = CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    fake_user_uid = "c2cf96e3-172e-4571-bb1a-71ed0f5ce037"
    uidb64 = urlsafe_base64_encode(smart_bytes(fake_user_uid))
    # token = PasswordResetTokenGenerator().make_token(user)
    bad_token = "faketn-4a85d1ec5dcbed69570c1b9721b3acca"
    redirect_url = ""
    resp = client.get(
        f"/auth/password-reset-confirm/{uidb64}/{bad_token}/?redirect_url={redirect_url}",
        follow=True
    )
    assert resp.status_code == 400
    assert "Token is invalid" in resp.data["error"]