"""get_resolved_locale: DB user_info.locale vs Accept-Language."""

import uuid
from unittest.mock import patch

import pytest
from starlette.requests import Request

from app.auth.dependencies import get_resolved_locale


def _request_with_accept(value: str) -> Request:
    headers = []
    if value:
        headers.append((b"accept-language", value.encode("ascii")))
    return Request({"type": "http", "headers": headers})


@pytest.fixture
def user_id():
    return uuid.uuid4()


def test_get_resolved_locale_prefers_database_locale(user_id):
    req = _request_with_accept("pt-BR")
    with patch("app.auth.dependencies.db_read", return_value={"locale": "es"}) as m:
        loc = get_resolved_locale(req, {"user_id": user_id}, db=object())
    assert loc == "es"
    m.assert_called_once()


def test_get_resolved_locale_falls_back_to_accept_language(user_id):
    req = _request_with_accept("pt-BR,en;q=0.8")
    with patch("app.auth.dependencies.db_read", return_value=None):
        loc = get_resolved_locale(req, {"user_id": user_id}, db=object())
    assert loc == "pt"
