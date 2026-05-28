import uuid
import inspect
from typing import Any, Callable, Dict, Optional, Type

_component_registry: Dict[str, "Component"] = {}
_mount_paths: Dict[str, str] = {}


class Component:
    _id: str = ""
    _mount_path: str = ""

    def __init__(self):
        self._id = uuid.uuid4().hex[:12]

    def url_for(self, action: str) -> str:
        return f"{self._mount_path}/{self._id}/{action}"

    def init(self):
        pass

    def render(self) -> str:
        raise NotImplementedError

    async def _handle_action(self, action: str, request) -> str:
        handler = getattr(self, action, None)
        if handler is None:
            return f"<div>Unknown action: {action}</div>"
        result = handler(request)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, str):
            return result
        return self.render()

    @property
    def id(self) -> str:
        return self._id


BASE_LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               max-width: 800px; margin: 0 auto; padding: 2rem; color: #333; line-height: 1.6; }
        h1, h2, h3 { margin-bottom: 0.5rem; }
        button, .btn { cursor: pointer; padding: 0.5rem 1rem; border: 1px solid #0070f3;
                       background: #0070f3; color: white; border-radius: 6px; font-size: 0.9rem; }
        button:hover { background: #005bb5; }
        input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 6px; font-size: 0.9rem; }
        .card { background: #f5f5f5; padding: 1.5rem; border-radius: 8px; margin: 1rem 0; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px;
                 background: #e0e0e0; font-size: 0.8rem; }
        nav a { margin-right: 1rem; color: #0070f3; text-decoration: none; }
        nav a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <nav>{nav}</nav>
    <main id="main">{content}</main>
</body>
</html>"""


def layout(title: str, content: str, nav: str = "") -> str:
    return BASE_LAYOUT.replace("{title}", title).replace("{content}", content).replace("{nav}", nav)


def mount(app, path: str, component_cls: Type[Component], title: str = "Apex Live"):
    from .request import HTMLResponse
    mount_path = path.rstrip("/")
    action_path = f"{mount_path}/{{comp_id}}/{{action}}"

    @app.get(path)
    async def _render(request):
        comp = component_cls()
        comp._mount_path = mount_path
        comp.init()
        _component_registry[comp._id] = comp
        _mount_paths[comp._id] = mount_path
        html = layout(title, comp.render(), nav=f'<a href="/">Home</a>')
        return HTMLResponse(content=html)

    @app.route(action_path, methods=["GET", "POST"])
    async def _handle_action(request):
        comp_id = request.path_params["comp_id"]
        action = request.path_params["action"]
        comp = _component_registry.get(comp_id)
        if comp is None:
            return HTMLResponse(content="<div>Component session expired</div>", status=404)
        result = await comp._handle_action(action, request)
        return HTMLResponse(content=result)


def include_htmx() -> str:
    return '<script src="https://unpkg.com/htmx.org@2.0.4"></script>'
