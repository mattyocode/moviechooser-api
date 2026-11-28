import runpy
from pathlib import Path
from unittest import mock

import pytest
from django.db import OperationalError
from django.test import override_settings

HEALTH_URL = "/api/health/"
BASE_SETTINGS = Path(__file__).resolve().parent.parent / "settings" / "base.py"


@pytest.fixture
def prod_security_settings(monkeypatch):
    """The redirect settings base.py applies when DEBUG is off.

    Tests run with DEBUG=1, so the real values never load; evaluate base.py
    again with DEBUG=0 to get them.
    """
    monkeypatch.setenv("DEBUG", "0")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "testserver")
    base = runpy.run_path(str(BASE_SETTINGS))
    return {
        "SECURE_SSL_REDIRECT": base["SECURE_SSL_REDIRECT"],
        "SECURE_REDIRECT_EXEMPT": base["SECURE_REDIRECT_EXEMPT"],
    }


@pytest.mark.django_db
def test_health_ok(client):
    resp = client.get(HEALTH_URL)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
def test_health_database_error(client):
    with mock.patch(
        "config.views.connection.cursor", side_effect=OperationalError("db down")
    ):
        resp = client.get(HEALTH_URL)
    assert resp.status_code == 503
    assert resp.json() == {"status": "error"}


@pytest.mark.django_db
def test_health_not_redirected_over_http(client, prod_security_settings):
    assert prod_security_settings["SECURE_SSL_REDIRECT"] is True
    with override_settings(**prod_security_settings):
        resp = client.get(HEALTH_URL, secure=False)
        # Control: other paths are still redirected to HTTPS.
        other = client.get("/api/movies/", secure=False)
    assert resp.status_code == 200
    assert other.status_code == 301


@pytest.mark.django_db
def test_health_needs_no_auth(client):
    # An invalid token would get a 401 from DRF's JWT authentication.
    resp = client.get(HEALTH_URL, HTTP_AUTHORIZATION="JWT not-a-valid-token")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
