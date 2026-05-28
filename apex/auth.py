import hashlib
import secrets
import time
from typing import Any, Callable, Dict, Optional

from .db import Model, Field, get_db, init_db


class User(Model):
    __tablename__ = "users"
    id = Field("INTEGER", primary_key=True)
    username = Field("TEXT", unique=True, nullable=False)
    email = Field("TEXT", unique=True, nullable=False)
    password_hash = Field("TEXT", nullable=False)
    created_at = Field("TEXT", default="CURRENT_TIMESTAMP")


class Session(Model):
    __tablename__ = "sessions"
    id = Field("INTEGER", primary_key=True)
    user_id = Field("INTEGER", nullable=False)
    token = Field("TEXT", unique=True, nullable=False)
    created_at = Field("TEXT", default="CURRENT_TIMESTAMP")
    expires_at = Field("TEXT")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, h = password_hash.split(":")
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def _create_token() -> str:
    return secrets.token_hex(32)


def init(app):
    init_db()
    from .request import HTMLResponse, RedirectResponse, Request

    @app.get("/register")
    async def register_page(request):
        return HTMLResponse(content=REGISTER_PAGE)

    @app.post("/register")
    async def register_action(request):
        form = await request.form()
        username = form.get("username", "").strip()
        email = form.get("email", "").strip()
        password = form.get("password", "").strip()
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters")
        if not email or "@" not in email:
            errors.append("Valid email required")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters")
        if User.get(username=username):
            errors.append("Username already taken")
        if User.get(email=email):
            errors.append("Email already registered")
        if errors:
            return HTMLResponse(content=REGISTER_PAGE.replace(
                "<!--errors-->",
                "".join(f'<div class="error">{e}</div>' for e in errors)
            ).replace('value=""', f'value="{username}"', 1))
        User.create(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        return RedirectResponse("/login")

    @app.get("/login")
    async def login_page(request):
        return HTMLResponse(content=LOGIN_PAGE)

    @app.post("/login")
    async def login_action(request):
        form = await request.form()
        username = form.get("username", "").strip()
        password = form.get("password", "").strip()
        user = User.get(username=username)
        if not user or not verify_password(password, user["password_hash"]):
            return HTMLResponse(content=LOGIN_PAGE.replace(
                "<!--errors-->",
                '<div class="error">Invalid username or password</div>'
            ))
        token = _create_token()
        Session.create(user_id=user["id"], token=token,
                       expires_at=str(time.time() + 86400 * 7))
        resp = RedirectResponse("/dashboard")
        resp.set_cookie("session", token, max_age=86400 * 7, path="/")
        return resp

    @app.get("/logout")
    async def logout(request):
        token = _get_token_from_request(request)
        if token:
            Session.delete(token=token)
        resp = RedirectResponse("/")
        resp.set_cookie("session", "", max_age=0, path="/")
        return resp


def _get_token_from_request(request) -> Optional[str]:
    return request.headers.get("cookie", "").split("session=")[-1].split(";")[0] if "session=" in request.headers.get("cookie", "") else None


def get_user(request) -> Optional[Dict[str, Any]]:
    if not hasattr(request, '_user'):
        token = _get_token_from_request(request)
        if token:
            session = Session.get(token=token)
            if session:
                user = User.get(id=session["user_id"])
                request._user = user
                return user
        request._user = None
    return request._user


def require(handler):
    import inspect as _inspect
    if _inspect.iscoroutinefunction(handler):
        async def wrapper(request, *args, **kwargs):
            user = get_user(request)
            if not user:
                from .request import RedirectResponse
                return RedirectResponse("/login")
            request.user = user
            return await handler(request, *args, **kwargs)
        return wrapper
    else:
        def wrapper(request, *args, **kwargs):
            user = get_user(request)
            if not user:
                from .request import RedirectResponse
                return RedirectResponse("/login")
            request.user = user
            return handler(request, *args, **kwargs)
        return wrapper


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login - Apex</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       max-width:400px; margin:2rem auto; padding:1rem; color:#333; }
h1 { margin-bottom:1rem; }
input { width:100%; padding:0.5rem; margin-bottom:0.75rem; border:1px solid #ccc;
        border-radius:6px; font-size:1rem; }
button { width:100%; padding:0.75rem; background:#0070f3; color:white; border:none;
         border-radius:6px; font-size:1rem; cursor:pointer; }
button:hover { background:#005bb5; }
.error { background:#fee; color:#c00; padding:0.5rem; border-radius:4px; margin-bottom:0.75rem; }
.card { background:#f5f5f5; padding:1.5rem; border-radius:8px; }
a { color:#0070f3; text-decoration:none; }
</style>
</head>
<body>
<div class="card">
<h1>Login</h1>
<!--errors-->
<form method="POST" action="/login">
  <input type="text" name="username" placeholder="Username" required>
  <input type="password" name="password" placeholder="Password" required>
  <button type="submit">Login</button>
</form>
<p style="margin-top:0.75rem;text-align:center;">Don't have an account? <a href="/register">Register</a></p>
</div>
</body>
</html>"""

REGISTER_PAGE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Register - Apex</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       max-width:400px; margin:2rem auto; padding:1rem; color:#333; }
h1 { margin-bottom:1rem; }
input { width:100%; padding:0.5rem; margin-bottom:0.75rem; border:1px solid #ccc;
        border-radius:6px; font-size:1rem; }
button { width:100%; padding:0.75rem; background:#0070f3; color:white; border:none;
         border-radius:6px; font-size:1rem; cursor:pointer; }
button:hover { background:#005bb5; }
.error { background:#fee; color:#c00; padding:0.5rem; border-radius:4px; margin-bottom:0.75rem; }
.card { background:#f5f5f5; padding:1.5rem; border-radius:8px; }
a { color:#0070f3; text-decoration:none; }
</style>
</head>
<body>
<div class="card">
<h1>Register</h1>
<!--errors-->
<form method="POST" action="/register">
  <input type="text" name="username" placeholder="Username (min 3 chars)" required>
  <input type="email" name="email" placeholder="Email" required>
  <input type="password" name="password" placeholder="Password (min 6 chars)" required>
  <button type="submit">Register</button>
</form>
<p style="margin-top:0.75rem;text-align:center;">Already have an account? <a href="/login">Login</a></p>
</div>
</body>
</html>"""
