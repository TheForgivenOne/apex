from typing import Any, Callable, Dict, List, Awaitable
import time
import logging

logger = logging.getLogger("apex")


class MiddlewareChain:
    def __init__(self):
        self._middleware: List[Callable] = []

    def add(self, middleware: Callable):
        self._middleware.append(middleware)

    async def process(self, request, handler) -> Any:
        async def dispatch(index: int) -> Any:
            if index < len(self._middleware):
                return await self._middleware[index](request, lambda: dispatch(index + 1))
            return await handler()
        return await dispatch(0)


class CORSMiddleware:
    def __init__(
        self,
        allow_origins: List[str] = None,
        allow_methods: List[str] = None,
        allow_headers: List[str] = None,
        allow_credentials: bool = True,
    ):
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.allow_headers = allow_headers or ["Content-Type", "Authorization"]
        self.allow_credentials = allow_credentials

    async def __call__(self, request, next_handler):
        if request.method == "OPTIONS":
            from .request import Response
            resp = Response(status=204)
            resp.headers["Access-Control-Allow-Origin"] = ", ".join(self.allow_origins)
            resp.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            resp.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            if self.allow_credentials:
                resp.headers["Access-Control-Allow-Credentials"] = "true"
            return resp
        response = await next_handler()
        origin = request.headers.get("origin", "*")
        if self.allow_origins == ["*"] or origin in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response


class LoggingMiddleware:
    async def __call__(self, request, next_handler):
        start = time.time()
        response = await next_handler()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{request.method} {request.path} -> {response.status} ({elapsed:.0f}ms)")
        return response
