"""Single-user access lock for a public Zeabur deployment.

If ``PAINRADAR_ADMIN_PASSWORD`` is set:

- ``/`` serves a small login form (HTTP 200) so Zeabur health probes succeed;
- posting the password to ``/login`` sets a signed cookie (30 days);
- every ``/api/*`` except ``/api/health`` still requires the cookie or Basic Auth;
- HTTP Basic Auth remains available for curl/scripts.

With no password configured (local development), the middleware is a no-op.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

COOKIE_NAME = "pr_auth"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60
PUBLIC_PATHS = {"/api/health", "/login", "/favicon.ico", "/static"}
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


def login_page(error: str = "") -> str:
    message = f'<p class="err">{error}</p>' if error else ""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PainRadar · 登录</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f8fafc;
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:32px 28px;
width:min(360px,88vw);box-shadow:0 12px 32px rgba(15,23,42,.08)}}
h1{{margin:0 0 6px;font-size:22px;color:#312e81}}
p{{margin:0 0 18px;color:#64748b;font-size:14px}}
input{{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #cbd5e1;
border-radius:9px;font-size:15px;margin-bottom:14px}}
button{{width:100%;padding:11px;border:0;border-radius:9px;background:#4338ca;color:#fff;
font-size:15px;font-weight:600;cursor:pointer}}
button:hover{{background:#3730a3}}
.err{{color:#b91c1c;font-size:13px;margin:0 0 12px}}
</style></head>
<body><form class="card" method="post" action="/login">
<h1>PainRadar · 机会雷达</h1>
<p>私人部署，请输入访问密码</p>
{message}
<input type="password" name="password" placeholder="访问密码" autofocus required>
<button type="submit">进入</button>
</form></body></html>"""


def _set_cookie(response, request: Request, expected: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        expected,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https",
    )


def install_auth(app: FastAPI) -> None:
    @app.get("/login")
    def login_form() -> HTMLResponse:
        if not _password():
            return HTMLResponse("", status_code=200)
        return HTMLResponse(login_page())

    @app.post("/login")
    async def login_submit(request: Request):
        password = _password()
        form = await request.form()
        supplied = str(form.get("password", ""))
        if password and hmac.compare_digest(supplied, password):
            response = RedirectResponse("/", status_code=303)
            _set_cookie(response, request, auth_token(password))
            return response
        return HTMLResponse(login_page("密码不正确"), status_code=401)

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

        authorization = request.headers.get("authorization", "")
        supplied = _basic_password(authorization)
        if supplied is not None:
            if hmac.compare_digest(supplied, password):
                response = await call_next(request)
                _set_cookie(response, request, expected)
                return response
            headers = {"WWW-Authenticate": 'Basic realm="PainRadar"'}
            if path.startswith("/api/"):
                return JSONResponse({"detail": "未授权"}, status_code=401, headers=headers)
            return PlainTextResponse("Authentication required", status_code=401, headers=headers)

        # No credentials: show the login form for the SPA entry (health probes get 200).
        if path == "/" and request.method in ("GET", "HEAD"):
            return HTMLResponse(login_page())

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
