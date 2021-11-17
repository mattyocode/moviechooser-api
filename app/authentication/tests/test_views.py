from unittest.mock import patch

import pytest

from accounts.models import CustomUser


@pytest.mark.django_db
def test_send_pw_reset_email_user_exists(client):
    CustomUser.objects.create_user(email="standard@user.com", password="testpw")
    with patch("authentication.views.send_mail") as mock_send_mail:
        resp = client.post(
            "/auth/request-reset-email/", data={"email": "standard@user.com"}
        )
        assert resp.status_code == 200
        assert resp.data["success"] == "Reset password email sent if account exists"
        args, kwargs = mock_send_mail.call_args
        assert "Reset your password" in args
        assert ["standard@user.com"] in args


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
