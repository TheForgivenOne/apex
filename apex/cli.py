#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
from pathlib import Path


TEMPLATE_PROJECT = {
    "app.py": """from apex import Apex

app = Apex()

@app.get("/")
async def home(request):
    return "<h1>Welcome to Apex!</h1><p>Your app is running.</p>"

if __name__ == "__main__":
    app.serve()
""",
    "pages/index.py": """from apex import HTMLResponse

async def handler(request):
    return HTMLResponse("<h1>Home</h1><p>File-based routing!</p>")
""",
    "pages/about.py": """async def handler(request):
    return "<h1>About</h1><p>This page uses file-based routing.</p>"
""",
    "pages/blog/[slug].py": """async def handler(request):
    slug = request.path_params.get("slug", "unknown")
    return f"<h1>Blog Post: {slug}</h1>"
""",
    "pages/api/hello.py": """from apex import JSONResponse

async def handler(request):
    return JSONResponse({"message": "Hello from API!"})
""",
    "public/style.css": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
h1 { color: #333; margin-bottom: 1rem; }
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
    (project_dir / "pages").mkdir(exist_ok=True)
    (project_dir / "pages" / "blog").mkdir(exist_ok=True)
    (project_dir / "pages" / "api").mkdir(exist_ok=True)
    (project_dir / "public").mkdir(exist_ok=True)
    (project_dir / "components").mkdir(exist_ok=True)
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
