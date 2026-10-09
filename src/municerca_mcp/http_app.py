"""HTTP transport (MCP streamable HTTP) for hosted deployments.

Every request except /healthz needs `Authorization: Bearer <MUNICERCA_AUTH_TOKEN>`. The
server refuses to start over HTTP without a token: there is no unauthenticated mode.
"""

from __future__ import annotations

import hmac
import os

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from municerca_mcp.server import mcp

MIN_TOKEN_LENGTH = 32
HEALTH_PATH = "/healthz"


@mcp.custom_route(HEALTH_PATH, methods=["GET"])  # type: ignore[untyped-decorator]
async def healthz(_: Request) -> Response:
    return JSONResponse({"status": "ok"})


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != HEALTH_PATH:
            supplied = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self._expected):
                response = JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


def build_app(token: str) -> ASGIApp:
    if len(token) < MIN_TOKEN_LENGTH:
        raise ValueError(f"MUNICERCA_AUTH_TOKEN must have at least {MIN_TOKEN_LENGTH} characters")
    # Stateless so any instance can answer any request. Host header checks are left to the
    # platform's front end, and the bearer token is the access control.
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )
    return BearerAuthMiddleware(mcp.streamable_http_app(), token)


def serve() -> None:
    token = os.environ.get("MUNICERCA_AUTH_TOKEN", "")
    try:
        app = build_app(token)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))  # noqa: S104
