#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
from pathlib import Path


TEMPLATE_PROJECT = {
    "app.py": """from apex import *

app = Apex(db_path="data.db")
setup_templates(["templates"])


class Task(Model):
    title: str
    done: bool


@app.get("/")
def home(request):
    tasks = Task.all()
    return render_template("index.html", tasks=tasks)


@app.post("/add")
async def add(request):
    form = await request.form()
    Task.create(title=form.get("title", "").strip(), done=False)
    return RedirectResponse("/")


@app.get("/done/{id}")
def mark_done(request):
    Task.update(where={"id": int(request.path_params["id"])}, values={"done": True})
    return RedirectResponse("/")


@app.get("/delete/{id}")
def delete_task(request):
    Task.delete(id=int(request.path_params["id"]))
    return RedirectResponse("/")


if __name__ == "__main__":
    app.serve()
""",
    "templates/layout.html": """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Apex Todo</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:system-ui,sans-serif; max-width:600px; margin:0 auto; padding:2rem; }
        h1 { margin-bottom:1rem; }
        a { color:#0070f3; text-decoration:none; }
        .card { background:#f9f9f9; padding:1rem; border-radius:8px; margin-bottom:0.5rem;
                display:flex; justify-content:space-between; align-items:center; }
        .done { text-decoration:line-through; color:#999; }
        form { display:flex; gap:0.5rem; margin-bottom:2rem; }
        input[type=text] { flex:1; padding:0.5rem; border:1px solid #ccc; border-radius:6px; font-size:1rem; }
        button { padding:0.5rem 1rem; background:#0070f3; color:white; border:none; border-radius:6px; cursor:pointer; }
        .empty { color:#999; text-align:center; padding:2rem; }
    </style>
</head>
<body>
    <h1>Todo</h1>
    <form method="POST" action="/add">
        <input type="text" name="title" placeholder="What needs to be done?" required>
        <button>Add</button>
    </form>
    <main>{% block content %}{% endblock %}</main>
</body>
</html>
""",
    "templates/index.html": """{% extends "layout.html" %}
{% block content %}
{% for task in tasks %}
    <div class="card">
        <span class="{% if task.done %}done{% endif %}">{{ task.title }}</span>
        <div>
            {% if not task.done %}<a href="/done/{{ task.id }}">Done</a>{% endif %}
            <a href="/delete/{{ task.id }}" style="color:#e00;">Delete</a>
        </div>
    </div>
{% endfor %}
{% if not tasks %}
    <div class="empty">No tasks yet. Add one above!</div>
{% endif %}
{% endblock %}
""",
    "README.md": """# Apex App

Built with [Apex](https://github.com/apex/apex) web framework.

## Run

```bash
pip install -e .
apex dev
```
"""
}


def new_command(args):
    project_dir = Path(args.name)
    if project_dir.exists():
        print(f"Error: Directory '{args.name}' already exists.")
        sys.exit(1)
    project_dir.mkdir(parents=True)
    (project_dir / "templates").mkdir(exist_ok=True)
    for filename, content in TEMPLATE_PROJECT.items():
        filepath = project_dir / filename
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_text(content)
    print(f"Created new Apex project at '{args.name}'")
    print(f"  cd {args.name}")
    print(f"  apex dev")


def dev_command(args):
    entry = args.entry or "app.py"
    entry_path = Path(entry)
    if not entry_path.exists():
        print(f"Error: '{entry}' not found.")
        sys.exit(1)
    os.environ["APEX_ENTRY"] = str(entry_path.absolute())
    port = args.port or 8080
    sys.path.insert(0, str(entry_path.parent.absolute()))
    exec(entry_path.read_text())


def run_command(args):
    entry = args.entry or "app.py"
    entry_path = Path(entry)
    if not entry_path.exists():
        print(f"Error: '{entry}' not found.")
        sys.exit(1)
    port = args.port or 8080
    os.environ["APEX_ENTRY"] = str(entry_path.absolute())
    sys.path.insert(0, str(entry_path.parent.absolute()))
    code = entry_path.read_text()
    code = code.replace('reload=True)', f'host="{args.host}", port={port})')
    exec(code)


def routes_command(args):
    entry = args.entry or "app.py"
    entry_path = Path(entry)
    if not entry_path.exists():
        print(f"Error: '{entry}' not found.")
        sys.exit(1)
    sys.path.insert(0, str(entry_path.parent.absolute()))
    namespace = {}
    exec(entry_path.read_text(), namespace)
    app = namespace.get("app")
    if app:
        print(f"\nRegistered routes ({app.router.count} total):")
        print("-" * 60)
        for route in app.router.routes:
            methods = ", ".join(route.methods)
            print(f"  {methods:20s} {route.path}")
        pages_dir = getattr(app, "pages_dir", None)
        if pages_dir and pages_dir.exists():
            print(f"\nFile-based routes ({pages_dir}):")
            print("-" * 60)
            for path in sorted(pages_dir.rglob("*.py")):
                if path.name.startswith("_"):
                    continue
                rel = path.relative_to(pages_dir)
                route_parts = []
                for part in rel.parts:
                    if part.startswith("[") and part.endswith("]"):
                        route_parts.append(f":{part[1:-1]}")
                    elif part.endswith(".py"):
                        stem = part[:-3]
                        if stem == "index":
                            continue
                        route_parts.append(stem)
                    else:
                        route_parts.append(part)
                route_path = "/" + "/".join(route_parts)
                print(f"  {'GET':20s} {route_path}")


def main():
    parser = argparse.ArgumentParser(description="Apex web framework CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    new_parser = subparsers.add_parser("new", help="Create a new project")
    new_parser.add_argument("name", help="Project name")

    dev_parser = subparsers.add_parser("dev", help="Start dev server")
    dev_parser.add_argument("entry", nargs="?", default="app.py", help="Entry point")
    dev_parser.add_argument("--port", "-p", type=int, default=8080, help="Port")

    run_parser = subparsers.add_parser("run", help="Start production server")
    run_parser.add_argument("entry", nargs="?", default="app.py", help="Entry point")
    run_parser.add_argument("--host", default="0.0.0.0", help="Host")
    run_parser.add_argument("--port", "-p", type=int, default=8080, help="Port")

    routes_parser = subparsers.add_parser("routes", help="List routes")
    routes_parser.add_argument("entry", nargs="?", default="app.py", help="Entry point")

    args = parser.parse_args()
    if args.command == "new":
        new_command(args)
    elif args.command == "dev":
        dev_command(args)
    elif args.command == "run":
        run_command(args)
    elif args.command == "routes":
        routes_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
