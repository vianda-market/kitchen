"""get_resolved_locale and get_resolved_locale_optional behavior."""

import uuid
from unittest.mock import patch

import pytest
from starlette.requests import Request

from app.auth.dependencies import get_resolved_locale, get_resolved_locale_optional


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


# get_resolved_locale_optional must set request.state.resolved_locale on every
# return path so that K3's catch-all exception handlers can read it via
# getattr(request.state, "resolved_locale", None) instead of re-resolving from
# the header. See translation-phase-2-design.md Q-S6.


def test_get_resolved_locale_optional_db_hit_sets_state(user_id):
    req = _request_with_accept("pt-BR")
    with patch("app.auth.dependencies.db_read", return_value={"locale": "es"}):
        loc = get_resolved_locale_optional(req, {"user_id": user_id}, db=object())
    assert loc == "es"
    assert req.state.resolved_locale == "es"


def test_get_resolved_locale_optional_header_fallback_sets_state(user_id):
    req = _request_with_accept("pt-BR,en;q=0.8")
    with patch("app.auth.dependencies.db_read", return_value=None):
        loc = get_resolved_locale_optional(req, {"user_id": user_id}, db=object())
    assert loc == "pt"
    assert req.state.resolved_locale == "pt"


def test_get_resolved_locale_optional_anonymous_sets_state():
    req = _request_with_accept("es-AR")
    loc = get_resolved_locale_optional(req, current_user=None, db=object())
    assert loc == "es"
    assert req.state.resolved_locale == "es"
