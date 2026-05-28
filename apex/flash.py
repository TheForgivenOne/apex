from typing import Dict, List, Optional, Tuple

SESSION_KEY = "_apex_flashes"


def flash(request, message: str, category: str = "info"):
    flashes = getattr(request, "_flashes", None)
    if flashes is None:
        flashes = []
        request._flashes = flashes
    flashes.append((category, message))


def get_flashed_messages(request) -> List[Tuple[str, str]]:
    flashes = getattr(request, "_flashes", [])
    request._flashes = []
    return flashes


def render_flashed(request, wrapper: str = "div", class_prefix: str = "flash") -> str:
    messages = get_flashed_messages(request)
    if not messages:
        return ""
    parts = []
    for category, message in messages:
        cls = f'{class_prefix} {class_prefix}-{category}' if category else class_prefix
        parts.append(f'<{wrapper} class="{cls}">{message}</{wrapper}>')
    return "".join(parts)


def flash_middleware(app):
    from .request import Request
    original_dispatch = app._dispatch

    async def wrapped_dispatch(request):
        resp = await original_dispatch(request)
        flashes = getattr(request, "_flashes", None)
        if flashes:
            import json
            cookie = request.headers.get("cookie", "")
            existing = {}
            for part in cookie.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    existing[k] = v
            resp.set_cookie("_apex_flash", json.dumps(flashes), path="/", httponly=True)
        return resp

    app._dispatch = wrapped_dispatch
