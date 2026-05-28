import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timezone


class Request:
    def __init__(self, scope: Dict[str, Any], receive):
        self.scope = scope
        self._receive = receive
        self.method = scope.get("method", "GET")
        self.path = scope.get("path", "/")
        self.scheme = scope.get("scheme", "http")
        self.query_string = scope.get("query_string", b"").decode("utf-8")
        self._body: Optional[bytes] = None
        self._headers = {
            k.decode("utf-8").lower(): v.decode("utf-8")
            for k, v in scope.get("headers", [])
        }
        self.path_params: Dict[str, str] = {}

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @property
    def query_params(self) -> Dict[str, str]:
        parsed = parse_qs(self.query_string)
        return {k: v[0] if v else "" for k, v in parsed.items()}

    @property
    def content_type(self) -> str:
        return self._headers.get("content-type", "")

    async def body(self) -> bytes:
        if self._body is None:
            chunks = []
            more_body = True
            while more_body:
                message = await self._receive()
                if message["type"] == "http.request":
                    chunks.append(message.get("body", b""))
                    more_body = message.get("more_body", False)
                else:
                    more_body = False
            self._body = b"".join(chunks)
        return self._body

    async def json(self) -> Any:
        return json.loads(await self.body())

    async def form(self) -> Dict[str, str]:
        body = await self.body()
        parsed = parse_qs(body.decode("utf-8"))
        return {k: v[0] if v else "" for k, v in parsed.items()}

    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path}>"


class Response:
    def __init__(
        self,
        content: Any = b"",
        status: int = 200,
        headers: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
    ):
        self.status = status
        self._headers: Dict[str, str] = headers or {}
        self._body: bytes = b""

        if isinstance(content, str):
            self._body = content.encode("utf-8")
            if content_type is None:
                content_type = "text/html; charset=utf-8"
        elif isinstance(content, bytes):
            self._body = content
        elif isinstance(content, dict) or isinstance(content, list):
            self._body = json.dumps(content, default=str).encode("utf-8")
            if content_type is None:
                content_type = "application/json"
        else:
            self._body = str(content).encode("utf-8")

        if content_type:
            self._headers["Content-Type"] = content_type
        if "Content-Type" not in self._headers:
            self._headers["Content-Type"] = "text/html; charset=utf-8"
        self._headers.setdefault("Content-Length", str(len(self._body)))

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    def set_cookie(
        self,
        key: str,
        value: str,
        max_age: Optional[int] = None,
        path: str = "/",
        secure: bool = False,
        httponly: bool = True,
        samesite: str = "Lax",
    ):
        cookie = f"{key}={value}"
        if max_age is not None:
            cookie += f"; Max-Age={max_age}"
        cookie += f"; Path={path}"
        if secure:
            cookie += "; Secure"
        if httponly:
            cookie += "; HttpOnly"
        cookie += f"; SameSite={samesite}"
        existing = self._headers.get("Set-Cookie", "")
        if existing:
            self._headers["Set-Cookie"] = existing + "\n" + cookie
        else:
            self._headers["Set-Cookie"] = cookie

    async def send(self, send_func):
        raw_headers = [
            (k.lower().encode("utf-8"), v.encode("utf-8"))
            for k, v in self._headers.items()
        ]
        await send_func({
            "type": "http.response.start",
            "status": self.status,
            "headers": raw_headers,
        })
        await send_func({
            "type": "http.response.body",
            "body": self._body,
        })


class HTMLResponse(Response):
    def __init__(self, content: str = "", status: int = 200, headers: Optional[Dict[str, str]] = None):
        super().__init__(content=content, status=status, headers=headers, content_type="text/html; charset=utf-8")


class JSONResponse(Response):
    def __init__(self, content: Any = None, status: int = 200, headers: Optional[Dict[str, str]] = None):
        super().__init__(content=content, status=status, headers=headers, content_type="application/json")


class RedirectResponse(Response):
    def __init__(self, location: str, status: int = 302, headers: Optional[Dict[str, str]] = None):
        headers = headers or {}
        headers["Location"] = location
        super().__init__(content=b"", status=status, headers=headers)
