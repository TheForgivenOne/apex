# Apex

**A Python web framework with server-stateful Live Components. Zero JavaScript required.**

Write interactive web applications in pure Python. Apex combines file-based routing, a built-in SQLite ORM, session-based auth, and Live Components with automatic HTMX wiring — so you can build real apps without touching JavaScript.

## Quick Start

```bash
pip install apex-web

# Create a blog in 60 seconds
```
```python
from apex import Apex, HTMLResponse, auth, db
from apex.db import Model, Field, init_db

app = Apex()
db.set_db_path("blog.db")
auth.init(app)
init_db()

class Post(Model):
    __tablename__ = "posts"
    id = Field("INTEGER", primary_key=True)
    title = Field("TEXT", nullable=False)
    body = Field("TEXT", nullable=False)
    author_id = Field("INTEGER", nullable=False)

@app.get("/")
async def home(request):
    posts = Post.all()
    return HTMLResponse(content=render_posts(posts))

@app.get("/new")
@auth.require
async def new_post(request):
    return HTMLResponse(content=NEW_POST_FORM)

@app.post("/new")
@auth.require
async def create_post(request):
    form = await request.form()
    Post.create(title=form["title"], body=form["body"], author_id=request.user["id"])
    return RedirectResponse("/")
```

## Live Components

Interactive UI components with server-side state, auto-wired via HTMX:

```python
from apex import Apex, live

app = Apex()

class Counter(live.Component):
    def init(self):
        self.count = 0
    def render(self):
        return f'''
        <div id="c{self.id}">
            Count: {self.count}
            <button hx-post="{self.url_for('add')}"
                    hx-target="#c{self.id}">+1</button>
        </div>'''
    def add(self, request):
        self.count += 1

app.live("/counter", Counter)
```

## Features

| Feature | Status |
|---|---|
| File-based routing | ✅ |
| Dynamic path params (`/blog/{slug}`) | ✅ |
| Live Components (state + HTMX) | ✅ |
| SQLite ORM (auto-migration) | ✅ |
| Session-based auth | ✅ |
| Auth decorator (`@auth.require`) | ✅ |
| JSON APIs | ✅ |
| Static file serving | ✅ |
| CORS + Logging middleware | ✅ |
| ASGI-native (uvicorn) | ✅ |
| CLI: `apex new`, `apex dev` | ✅ |
| Docker support | ✅ |

## Run the demo blog

```bash
pip install apex-web
git clone https://github.com/apex/apex
cd apex/blog
python app.py
```

## Deploy

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install apex-web
CMD ["python", "app.py"]
```

## License

MIT
