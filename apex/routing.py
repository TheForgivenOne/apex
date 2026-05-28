import re
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple
from dataclasses import dataclass, field


@dataclass
class Route:
    path: str
    handler: Callable
    methods: List[str] = field(default_factory=lambda: ["GET"])
    name: Optional[str] = None
    middleware: List[Callable] = field(default_factory=list)

    _pattern: Optional[Pattern] = field(init=False, default=None)
    _param_names: List[str] = field(init=False, default_factory=list)

    def __post_init__(self):
        self._pattern, self._param_names = self._compile()

    def _compile(self) -> Tuple[Pattern, List[str]]:
        parts = self.path.strip("/").split("/") if self.path.strip("/") else []
        param_names: List[str] = []
        regex_parts: List[str] = []
        for part in parts:
            if part.startswith("{") and part.endswith("}"):
                name = part[1:-1].split(":")[0]
                param_names.append(name)
                regex_parts.append(f"(?P<{name}>[^/]+)")
            else:
                regex_parts.append(re.escape(part))
        pattern = "^/" + "/".join(regex_parts) + "$"
        return re.compile(pattern), param_names

    def match(self, path: str) -> Optional[Dict[str, str]]:
        match = self._pattern.match(path)
        if match:
            return match.groupdict()
        return None


class Router:
    def __init__(self):
        self.routes: List[Route] = []
        self._static_routes: Dict[str, List[Route]] = {}
        self._dynamic_routes: List[Route] = []

    def add(
        self,
        path: str,
        handler: Callable,
        methods: Optional[List[str]] = None,
        name: Optional[str] = None,
    ):
        route = Route(path, handler, methods or ["GET"], name)
        self.routes.append(route)
        if "{" in path:
            self._dynamic_routes.append(route)
        else:
            self._static_routes.setdefault(path, []).append(route)
        return route

    def resolve(self, path: str, method: str = "GET") -> Optional[Tuple[Callable, Dict[str, str]]]:
        path = path.rstrip("/") or "/"
        if path in self._static_routes:
            for route in self._static_routes[path]:
                if method in route.methods or method == "HEAD":
                    return route.handler, {}
        for route in self._dynamic_routes:
            if method not in route.methods and method != "HEAD":
                continue
            params = route.match(path)
            if params is not None:
                return route.handler, params
        return None

    def url_for(self, name: str, **params) -> Optional[str]:
        for route in self.routes:
            if route.name == name:
                path = route.path
                for key, value in params.items():
                    path = path.replace("{" + key + "}", str(value))
                return path
        return None

    def include_router(self, prefix: str, router: "Router"):
        for route in router.routes:
            new_path = prefix.rstrip("/") + "/" + route.path.lstrip("/")
            self.add(new_path, route.handler, route.methods, route.name)

    @property
    def count(self) -> int:
        return len(self.routes)


class FileSystemRouter:
    def __init__(self, pages_dir: str):
        self.pages_dir = pages_dir
        self.routes: Dict[str, Route] = {}

    def scan(self) -> Dict[str, Route]:
        from pathlib import Path
        base = Path(self.pages_dir)
        if not base.exists():
            return {}
        self.routes = {}
        for path in base.rglob("*.py"):
            if path.name.startswith("_"):
                continue
            relative = path.relative_to(base)
            parts = list(relative.parts)
            route_parts = []
            for part in parts:
                if part.endswith(".py"):
                    stem = part[:-3]
                else:
                    stem = part
                if stem.startswith("[") and stem.endswith("]"):
                    param = stem[1:-1]
                    route_parts.append(f"{{{param}}}")
                elif stem == "index":
                    continue
                else:
                    route_parts.append(stem)
            route_path = "/" + "/".join(route_parts)
            self.routes[route_path] = path
        return self.routes

    def get_handler(self, path: Path):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location(f"page_{path.stem}", path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
        return None
