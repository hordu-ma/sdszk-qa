from __future__ import annotations

import pytest
from fastapi import Request, Response
from starlette.types import Receive, Scope, Send

from src.apps.api.middleware import AuthContextMiddleware
from src.apps.api.rate_limit import get_user_identifier
from src.apps.api.utils.jwt import create_access_token


def _build_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers or [],
        "client": ("203.0.113.10", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_get_user_identifier_prefers_user_id() -> None:
    request = _build_request()
    request.state.user_id = "42"

    assert get_user_identifier(request) == "user:42"


def test_get_user_identifier_falls_back_to_ip() -> None:
    request = _build_request()

    assert get_user_identifier(request) == "203.0.113.10"


@pytest.mark.asyncio
async def test_auth_context_middleware_sets_user_id_from_jwt() -> None:
    token = create_access_token({"sub": "123"})
    request = _build_request(
        headers=[(b"authorization", f"Bearer {token}".encode())],
    )

    async def _dummy_app(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        return None

    middleware = AuthContextMiddleware(app=_dummy_app)

    async def call_next(req: Request) -> Response:
        assert req.state.user_id == "123"
        return Response("ok")

    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
