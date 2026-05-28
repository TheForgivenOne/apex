# Apex

**A Python web framework with server-stateful Live Components. Zero JavaScript required.**

Write interactive web applications in pure Python. Apex combines a built-in SQLite ORM,
session-based auth, a template engine with inheritance and filters, file-based routing,
and Live Components with automatic HTMX wiring — so you can build real apps without
touching JavaScript.

```bash
pip install apex-web
```

## Quick Start

```python
from apex import *

app = Apex(db_path="app.db")
setup_templates(["templates"])


@app.get("/")
def home(request):
    return render_template("index.html", name="World")


if __name__ == "__main__":
    app.serve()
```

```html
<!-- templates/layout.html -->
<!DOCTYPE html>
<html>
<body>
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
```

```html
<!-- templates/index.html -->
{% extends "layout.html" %}
{% block content %}
<h1>Hello, {{ name }}!</h1>
{% endblock %}
```

## Features

| Feature | Status |
|---|---|
| **TRIE-based routing** with path params (`/blog/{slug}`) | ✅ |
| **SQLite ORM** — auto-creates tables from type annotations | ✅ |
| **Template engine** — inheritance, blocks, filters, slicing | ✅ |
| **Live Components** — server state + auto-HTMX wiring | ✅ |
| **Session-based auth** — register, login, logout out of the box | ✅ |
| **Form handling** — field types, validators, CSRF, auto-render | ✅ |
| **Flash messages** — one-shot success/error after redirects | ✅ |
| **File-based routing** — Next.js-style `pages/` directory | ✅ |
| **ASGI-native** — runs on uvicorn | ✅ |
| **CLI** — `apex new`, `apex dev`, `apex run`, `apex routes` | ✅ |
| **Middlewares** — CORS, logging | ✅ |

---

## Template Engine

Supports extends, blocks, includes, for loops, if/else, filters, slicing, and auto-escaping.

```html
{% extends "layout.html" %}

{% block title %}{{ post.title|upper }}{% endblock %}

{% block content %}
  <h1>{{ post.title }}</h1>
  <p>{{ post.body|truncate(200) }}</p>

  <ul>
  {% for comment in comments %}
    <li>{{ comment.author }}: {{ comment.body }}</li>
  {% endfor %}
  </ul>

  {% if not comments %}
    <p>No comments yet.</p>
  {% endif %}
{% endblock %}
```

### Built-in Filters

`upper` · `lower` · `capitalize` · `title` · `trim` · `length` · `urlencode` · `safe` · `int` · `join(sep)` · `default(val)` · `truncate(n, suffix)`

### Slicing

```html
{{ post.body[:200] }}
{{ items[1:3] }}
{{ items|join(", ")|upper }}
```

---

## SQLite ORM

Models are defined with type annotations — tables are created automatically.

```python
class Post(Model):
    title: str
    body: str
    author_id: int
    published: bool

# All CRUD operations
Post.create(title="Hello", body="...", author_id=1, published=True)
post = Post.get(id=1)
posts = Post.filter(author_id=1, published=True)
Post.update(where={"id": 1}, values={"title": "Updated"})
Post.delete(id=1)

# Raw SQL
rows = Post.raw("SELECT p.*, u.name FROM posts p JOIN users u ON p.author_id = u.id")
```

Each model gets automatic `id` (INTEGER PRIMARY KEY) and `created_at` (TEXT with CURRENT_TIMESTAMP) fields.

---

## Live Components

Interactive UI components with server-side state. No JavaScript required — HTMX handles the wiring.

```python
from apex import Apex

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

---

## Auth

```python
from apex import auth

auth.init(app)

@app.get("/dashboard")
@auth.require
def dashboard(request):
    return f"Welcome, {request.user['username']}!"
```

Includes register, login, logout routes, password hashing, and session management.

---

## Forms

```python
from apex.forms import Form, StringField, EmailField, PasswordField, Required, Email, MinLength

class RegisterForm(Form):
    username = StringField(validators=[Required(), MinLength(3)])
    email = EmailField(validators=[Required(), Email()])
    password = PasswordField(validators=[Required(), MinLength(6)])

# In a route:
form = RegisterForm(data).skip_csrf()
if form.validate():
    # process
    return RedirectResponse("/dashboard")
return render_template("register.html", form=form.render())
```

Field types: `StringField` · `EmailField` · `PasswordField` · `TextAreaField` · `BooleanField` · `SelectField`

Validators: `Required` · `Email` · `MinLength` · `MaxLength` · `Match`

---

## CLI

```bash
# Create a new project
apex new myapp
cd myapp

# Start development server
apex dev

# Production
apex run --port 8000

# List routes
apex routes
```

---

## Run the Demo Blog

```bash
git clone https://github.com/TheForgivenOne/apex
cd apex/blog
pip install -e ..
python app3.py
```

Open http://localhost:8080 — full blog with auth, posts, comments, and flash messages.

---

## Project Structure

```
apex/
├── apex/               # Framework source
│   ├── app.py          # ASGI application, routing, lifespan
│   ├── routing.py      # TRIE and file-system routing
│   ├── request.py      # Request/Response/HTMLResponse/JSONResponse
│   ├── template.py     # Template engine with extends/blocks/filters
│   ├── db.py           # SQLite ORM with Model, Field, migrations
│   ├── auth.py         # Auth: register, login, logout, sessions
│   ├── forms.py        # Form fields, validators, CSRF
│   ├── flash.py        # One-shot flash messages
│   ├── live.py         # Live server-stateful components
│   ├── middleware.py   # CORS, logging middleware
│   ├── cli.py          # CLI: new, dev, run, routes
│   └── hotreload.py    # File watcher for dev server
├── blog/               # Demo blog application
│   ├── app3.py         # Showcase app (templates + forms + auth)
│   └── templates/      # HTML templates
├── demo/               # Demo apps
│   ├── app.py          # Basic routing demo
│   └── live_app.py     # Live Components demo
└── setup.py            # Package setup
```

## License

MIT
