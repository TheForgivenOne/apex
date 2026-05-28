from apex import Apex, Request, HTMLResponse, JSONResponse, CORSMiddleware, LoggingMiddleware

app = Apex()

app.add_middleware(LoggingMiddleware())
app.add_middleware(CORSMiddleware())

app.mount_static("public")

app.mount_pages("pages")

todos = [
    {"id": 1, "text": "Learn Apex", "done": True},
    {"id": 2, "text": "Build something great", "done": False},
    {"id": 3, "text": "Ship to production", "done": False},
]


@app.get("/")
async def home(request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Apex Framework</title>
        <link rel="stylesheet" href="/static/style.css">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
        <nav style="display:flex;gap:1rem;margin-bottom:2rem;padding:1rem 0;border-bottom:1px solid #eee;">
            <a href="/" style="font-weight:bold;color:#0070f3;">Home</a>
            <a href="/about">About</a>
            <a href="/api/todos">API: Todos</a>
            <a href="/blog/hello-world">Blog: Hello World</a>
        </nav>
        <h1>Welcome to Apex</h1>
        <p style="color:#666;margin-bottom:2rem;">A modern Python web framework with file-based routing.</p>
        <div style="background:#f5f5f5;padding:1.5rem;border-radius:8px;margin-bottom:2rem;">
            <h2>Quick Start</h2>
            <pre style="background:#1e1e1e;color:#d4d4d4;padding:1rem;border-radius:4px;overflow-x:auto;">
# app.py
from apex import Apex

app = Apex()

@app.get("/")
async def home(request):
    return "&lt;h1&gt;Hello, World!&lt;/h1&gt;"

if __name__ == "__main__":
    app.serve()
            </pre>
        </div>
        <div style="background:#0070f3;color:white;padding:1.5rem;border-radius:8px;">
            <h2>Features</h2>
            <ul style="margin-top:0.5rem;padding-left:1.5rem;">
                <li>File-based routing (like Next.js)</li>
                <li>ASGI-native, async by default</li>
                <li>Built-in static file serving</li>
                <li>CORS middleware</li>
                <li>Request logging</li>
                <li>Path parameters: /blog/{slug}</li>
                <li>JSON API support</li>
                <li>Hot reload in development</li>
            </ul>
        </div>
    </body>
    </html>
    """)


@app.get("/about")
async def about(request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>About - Apex</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <nav style="display:flex;gap:1rem;margin-bottom:2rem;padding:1rem 0;border-bottom:1px solid #eee;">
            <a href="/">Home</a>
            <a href="/about" style="font-weight:bold;color:#0070f3;">About</a>
        </nav>
        <h1>About Apex</h1>
        <p>Apex is a modern Python web framework built for the next generation of web applications.</p>
        <p>It combines file-based routing with ASGI performance, giving you the best of both worlds: simplicity and speed.</p>
        <p style="margin-top:2rem;"><a href="/" style="color:#0070f3;">&larr; Back home</a></p>
    </body>
    </html>
    """)


@app.get("/api/todos")
async def get_todos(request):
    return JSONResponse({"todos": todos})


@app.get("/api/todos/{id}")
async def get_todo(request):
    todo_id = int(request.path_params.get("id", 0))
    for todo in todos:
        if todo["id"] == todo_id:
            return JSONResponse(todo)
    return JSONResponse({"error": "Not found"}, status=404)


if __name__ == "__main__":
    app.serve()
