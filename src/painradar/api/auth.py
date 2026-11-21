"""Single-user access lock for a public Zeabur deployment.

If ``PAINRADAR_ADMIN_PASSWORD`` is set, every route except ``/api/health`` and
static assets requires the password:

- HTTP Basic Auth (username is ignored) — works in any browser/mobile prompt;
- on success a signed ``pr_auth`` cookie remembers the browser for 30 days.

With no password configured (local development), the middleware is a no-op.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

COOKIE_NAME = "pr_auth"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
PUBLIC_PATHS = {"/api/health", "/favicon.ico", "/static"}
PUBLIC_PREFIXES = ("/static/",)


def _password() -> str:
    return os.environ.get("PAINRADAR_ADMIN_PASSWORD", "").strip()


def auth_token(password: str) -> str:
    return hmac.new(password.encode(), b"painradar-auth-v1", hashlib.sha256).hexdigest()


def _basic_password(header: str) -> str | None:
    if not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except Exception:  # noqa: BLE001
        return None
    return decoded.split(":", 1)[1] if ":" in decoded else decoded


def install_auth(app: FastAPI) -> None:
    @app.middleware("http")
    async def admin_auth(request: Request, call_next):
        password = _password()
        if not password:
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        expected = auth_token(password)
        if hmac.compare_digest(request.cookies.get(COOKIE_NAME, ""), expected):
            return await call_next(request)

        supplied = _basic_password(request.headers.get("authorization", ""))
        if supplied is not None and hmac.compare_digest(supplied, password):
            response = await call_next(request)
            response.set_cookie(
                COOKIE_NAME,
                expected,
                max_age=COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https"
                or request.headers.get("x-forwarded-proto") == "https",
            )
            return response

        headers = {"WWW-Authenticate": 'Basic realm="PainRadar"'}
        if path.startswith("/api/"):
            return JSONResponse(
                {"detail": "未授权：请输入 PAINRADAR_ADMIN_PASSWORD"},
                status_code=401,
                headers=headers,
            )
        return PlainTextResponse("Authentication required", status_code=401, headers=headers)

    @app.get("/api/logout")
    def logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME)
        return response
