import importlib
import inspect
import os
import sys
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union
from types import ModuleType

from .routing import Router, FileSystemRouter, Route
from .request import Request, Response, HTMLResponse, JSONResponse
from .middleware import MiddlewareChain
from .template import Template, TemplateLoader

logger = logging.getLogger("apex")

HTMX_SRC = "https://unpkg.com/htmx.org@2.0.4"


class Apex:
    def __init__(self, name: str = "apex", db_path: Optional[str] = None):
        self.name = name
        self.router = Router()
        self.middleware = MiddlewareChain()
        self.template_loader = TemplateLoader([])
        self.pages_dir: Optional[Path] = None
        self.components_dir: Optional[Path] = None
        self.static_dir: Optional[Path] = None
        self._file_routes: Dict[str, Path] = {}
        self._cached_modules: Dict[str, ModuleType] = {}
        self._startup_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []
        self._exception_handlers: Dict[Type[Exception], Callable] = {}
        self._static_prefix = "/static"
        self._auth_inited = False
        if db_path:
            from . import db as _db
            _db.set_db_path(db_path)
        self._db_ready = bool(db_path)

    def route(self, path: str, methods: Optional[List[str]] = None, name: Optional[str] = None):
        def decorator(handler):
            self.router.add(path, handler, methods, name)
            return handler
        return decorator

    def get(self, path: str, name: Optional[str] = None):
        return self.route(path, methods=["GET"], name=name)

    def post(self, path: str, name: Optional[str] = None):
        return self.route(path, methods=["POST"], name=name)

    def put(self, path: str, name: Optional[str] = None):
        return self.route(path, methods=["PUT"], name=name)

    def delete(self, path: str, name: Optional[str] = None):
        return self.route(path, methods=["DELETE"], name=name)

    def patch(self, path: str, name: Optional[str] = None):
        return self.route(path, methods=["PATCH"], name=name)

    def on_startup(self, handler):
        self._startup_handlers.append(handler)
        return handler

    def on_shutdown(self, handler):
        self._shutdown_handlers.append(handler)
        return handler

    def exception_handler(self, exc_class: Type[Exception]):
        def decorator(handler):
            self._exception_handlers[exc_class] = handler
            return handler
        return decorator

    def add_middleware(self, middleware):
        self.middleware.add(middleware)
        return middleware

    def live(self, path: str, component_cls, title: str = "Apex Live"):
        from . import live as _live
        _live.mount(self, path, component_cls, title=title)

    def mount_static(self, directory: str, prefix: str = "/static"):
        self.static_dir = Path(directory)
        self._static_prefix = prefix.rstrip("/")

    def mount_pages(self, directory: str):
        self.pages_dir = Path(directory)
        self.components_dir = self.pages_dir.parent / "components"
        if not self.components_dir.exists():
            self.components_dir = self.pages_dir / ".." / "components"

    def _load_module(self, path: Path) -> Optional[ModuleType]:
        rel_path = path.relative_to(self.pages_dir) if self.pages_dir else path
        module_name = f"_apex_pages_{rel_path.parent.stem}_{path.stem}"
        module_name = module_name.replace("-", "_").replace(".", "_")
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                self._cached_modules[module_name] = module
                spec.loader.exec_module(module)
                return module
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
        return None

    def _scan_pages(self):
        if not self.pages_dir or not self.pages_dir.exists():
            return
        fs_router = FileSystemRouter(str(self.pages_dir))
        routes = fs_router.scan()
        self._file_routes = {}
        for route_path, file_path in routes.items():
            self._file_routes[route_path] = file_path

    def _resolve_file_route(self, path: str) -> Optional[Any]:
        import re as _re
        path = path.rstrip("/") or "/"
        for route_path, file_path in self._file_routes.items():
            route_parts = route_path.strip("/").split("/") if route_path.strip("/") else []
            pattern_parts = []
            param_names = []
            for part in route_parts:
                if part.startswith("{") and part.endswith("}"):
                    param_names.append(part[1:-1])
                    pattern_parts.append("([^/]+)")
                else:
                    pattern_parts.append(_re.escape(part))
            pattern = "^/" + "/".join(pattern_parts) + "$"
            match = _re.match(pattern, path)
            if match:
                module = self._load_module(file_path)
                if module:
                    handler = (
                        getattr(module, "handler", None)
                        or getattr(module, "page", None)
                        or getattr(module, "get", None)
                    )
                    if handler:
                        params = dict(zip(param_names, match.groups()))
                        async def _wrapped(req, _handler=handler, _params=params):
                            req.path_params = {**req.path_params, **_params}
                            if inspect.iscoroutinefunction(_handler):
                                return await _handler(req)
                            return _handler(req)
                        return _wrapped
                break
        return None

    def _handle_static(self, path: str) -> Optional[Response]:
        if not self.static_dir or not path.startswith(self._static_prefix):
            return None
        rel_path = path[len(self._static_prefix):].lstrip("/")
        file_path = self.static_dir / rel_path
        if not file_path.exists() or not file_path.is_file():
            return None
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            mime_type = "application/octet-stream"
        content = file_path.read_bytes()
        resp = Response(content=content, content_type=mime_type)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    async def _dispatch(self, request: Request) -> Response:
        path = request.path.rstrip("/") or "/"

        static_resp = self._handle_static(path)
        if static_resp:
            return static_resp

        result = self.router.resolve(path, request.method)
        if result:
            handler, params = result
            request.path_params = params
            try:
                if inspect.iscoroutinefunction(handler):
                    response = await handler(request)
                else:
                    response = handler(request)
                response = self._auto_response(response)
                return response
            except Exception as e:
                return await self._handle_exception(request, e)

        file_handler = self._resolve_file_route(path)
        if file_handler:
            try:
                if callable(file_handler):
                    if inspect.iscoroutinefunction(file_handler):
                        response = await file_handler(request)
                    else:
                        response = file_handler(request)
                    response = self._auto_response(response)
                    return response
            except Exception as e:
                return await self._handle_exception(request, e)

        return HTMLResponse(content="<h1>404 Not Found</h1>", status=404)

    def _auto_response(self, response: Any) -> Response:
        if isinstance(response, Response):
            return response
        if isinstance(response, dict) or isinstance(response, list):
            return JSONResponse(content=response)
        return HTMLResponse(content=str(response))

    async def _handle_exception(self, request: Request, exc: Exception) -> Response:
        exc_type = type(exc)
        if exc_type in self._exception_handlers:
            handler = self._exception_handlers[exc_type]
            if inspect.iscoroutinefunction(handler):
                return await handler(request, exc)
            return handler(request, exc)
        for parent_type in self._exception_handlers:
            if issubclass(exc_type, parent_type):
                handler = self._exception_handlers[parent_type]
                if inspect.iscoroutinefunction(handler):
                    return await handler(request, exc)
                return handler(request, exc)
        logger.exception(f"Unhandled exception for {request.method} {request.path}")
        return HTMLResponse(content=f"<h1>500 Internal Server Error</h1><pre>{exc}</pre>", status=500)

    async def __call__(self, scope: Dict[str, Any], receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            response = await self.middleware.process(request, lambda: self._dispatch(request))
            await response.send(send)
        elif scope["type"] == "lifespan":
            message = await receive()
            if message["type"] == "lifespan.startup":
                for handler in self._startup_handlers:
                    if inspect.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                for handler in self._shutdown_handlers:
                    if inspect.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                await send({"type": "lifespan.shutdown.complete"})

    def _reload_modules(self):
        self._cached_modules.clear()
        self._file_routes.clear()
        if self.pages_dir:
            self._scan_pages()

    def serve(self, host: str = "0.0.0.0", port: int = 8080, reload: bool = False, log_level: str = "info"):
        logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
        if self._db_ready:
            from . import db as _db
            _db.init_db()
        if self.pages_dir:
            self._scan_pages()
        import uvicorn
        uvicorn.run(self, host=host, port=port, log_level=log_level)


_app_instance: Optional[Apex] = None


def create_app(name: str = "apex") -> Apex:
    global _app_instance
    app = Apex(name)
    _app_instance = app
    return app


def get_app() -> Apex:
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    return _app_instance
