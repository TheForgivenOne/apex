"""Apex Blog — simplified with the improved DX.

Run: python app2.py
"""

from apex import *

app = Apex(db_path="/tmp/apex2.db")
auth.init(app)


class Post(Model):
    title: str
    body: str
    author_id: int


class Comment(Model):
    post_id: int
    author: str
    body: str


LAYOUT_T = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       max-width:800px; margin:0 auto; padding:2rem; color:#333; line-height:1.6; }}
h1 {{ margin-bottom:1rem; }}
a {{ color:#0070f3; }}
.btn {{ display:inline-block; padding:0.5rem 1rem; border:1px solid #ccc; border-radius:6px;
       background:white; color:#333; cursor:pointer; font-size:0.9rem; }}
.btn-primary {{ background:#0070f3; color:white; border-color:#0070f3; }}
.post-card {{ background:#f9f9f9; padding:1.5rem; border-radius:8px; margin-bottom:1rem; }}
.meta {{ color:#888; font-size:0.85rem; }}
.flash {{ background:#d4edda; color:#155724; padding:0.75rem; border-radius:6px; margin-bottom:1rem; }}
form input, form textarea {{ width:100%; padding:0.75rem; border:1px solid #ccc; border-radius:6px;
    font-size:1rem; margin-bottom:1rem; font-family:inherit; }}
form textarea {{ min-height:200px; }}
</style></head>
<body>
<nav style="display:flex;gap:1rem;margin-bottom:2rem;border-bottom:1px solid #eee;padding-bottom:1rem;">
<a href="/" style="font-weight:bold;color:#111;">Apex Blog</a>
<span style="flex:1;"></span>
{{nav}}
</nav>
<main>{{content}}</main>
</body></html>"""


def layout(title, content, nav=""):
    return LAYOUT_T.replace("{{title}}", title).replace("{{content}}", content).replace("{{nav}}", nav)


def user_bar(user):
    if user:
        return f'Hi <strong>{user["username"]}</strong> | <a href="/dashboard">Dashboard</a> | <a href="/new">Write</a> | <a href="/logout">Logout</a>'
    return '<a href="/login">Login</a> | <a href="/register">Register</a>'


@app.get("/")
def home(request):
    user = auth.get_user(request)
    posts = Post.raw("SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id ORDER BY p.created_at DESC")
    items = "".join(
        f'<div class="post-card"><h2><a href="/post/{p["id"]}">{p["title"]}</a></h2>'
        f'<p class="meta">by {p["username"]}</p><p>{p["body"][:200]}</p></div>'
        for p in posts
    ) or '<p style="color:#999;text-align:center;padding:2rem;">No posts yet.</p>'
    return layout("Home", items, user_bar(user))


@app.get("/post/{id}")
def view_post(request):
    user = auth.get_user(request)
    post_id = int(request.path_params["id"])
    rows = Post.raw("SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id WHERE p.id=?", [post_id])
    if not rows:
        return HTMLResponse(layout("404", "<h1>404</h1>"), status=404)
    post = rows[0]
    comments = "".join(
        f'<div class="comment" style="padding:0.5rem 0;border-bottom:1px solid #eee;">'
        f'<strong>{c["author"]}</strong> <span class="meta">{c["created_at"]}</span><p>{c["body"]}</p></div>'
        for c in Comment.filter(post_id=post_id)
    ) or "<p>No comments yet.</p>"

    return layout(post["title"], f"""
        <p><a href="/">&larr; Back</a></p>
        <h1>{post["title"]}</h1>
        <p class="meta">by {post["username"]}</p>
        <div style="margin:1.5rem 0;">{post["body"]}</div>
        <hr>
        <h3>Comments</h3>
        <div id="comments">{comments}</div>
        <div class="post-card" style="margin-top:1rem;">
            <form hx-post="/comment/{post_id}" hx-target="#comments" hx-swap="beforeend"
                  hx-on::after-request="this.reset()">
                <input name="author" placeholder="Name" required style="width:200px;">
                <textarea name="body" placeholder="Comment..." required style="min-height:60px;"></textarea>
                <button class="btn btn-primary">Post</button>
            </form>
        </div>
    """, user_bar(user))


@app.post("/comment/{id}")
async def add_comment(request):
    post_id = int(request.path_params["id"])
    form = await request.form()
    Comment.create(post_id=post_id, author=form.get("author"), body=form.get("body"))
    c = Comment.filter(post_id=post_id)[-1]
    return f'<div style="padding:0.5rem 0;border-bottom:1px solid #eee;">' \
           f'<strong>{c["author"]}</strong> <span class="meta">{c["created_at"]}</span><p>{c["body"]}</p></div>'


@app.get("/dashboard")
@auth.require
def dashboard(request):
    user = request.user
    posts = Post.filter(author_id=user["id"])
    items = "".join(
        f'<div class="post-card" style="display:flex;justify-content:space-between;">'
        f'<div><strong><a href="/post/{p["id"]}">{p["title"]}</a></strong> <span class="meta">{p["created_at"]}</span></div>'
        f'<div><a href="/edit/{p["id"]}" class="btn btn-sm">Edit</a>'
        f' <a href="/delete/{p["id"]}" class="btn btn-sm" style="background:#e00;color:white;"'
        f' onclick="return confirm(\'Delete?\')">Delete</a></div></div>'
        for p in posts
    ) or '<p>No posts yet. <a href="/new">Write one!</a></p>'
    return layout("Dashboard", f'<h1>Dashboard</h1><p class="meta">Hi {user["username"]}</p><h3>Your Posts</h3>{items}', user_bar(user))


@app.get("/new")
@auth.require
def new_post(request):
    return layout("New Post", """
        <h1>New Post</h1>
        <form method="POST" action="/new">
            <input name="title" placeholder="Title" required>
            <textarea name="body" placeholder="Write your post..." required></textarea>
            <button class="btn btn-primary">Publish</button>
        </form>
    """)


@app.post("/new")
@auth.require
async def create_post(request):
    form = await request.form()
    Post.create(title=form["title"], body=form["body"], author_id=request.user["id"])
    return RedirectResponse("/")


@app.get("/edit/{id}")
@auth.require
def edit_post(request):
    post = Post.get(id=int(request.path_params["id"]))
    if not post or post["author_id"] != request.user["id"]:
        return RedirectResponse("/")
    return layout("Edit Post", f"""
        <h1>Edit Post</h1>
        <form method="POST" action="/edit/{post["id"]}">
            <input name="title" value="{post["title"]}" required>
            <textarea name="body" required>{post["body"]}</textarea>
            <button class="btn btn-primary">Update</button>
        </form>
    """)


@app.post("/edit/{id}")
@auth.require
async def update_post(request):
    post_id = int(request.path_params["id"])
    form = await request.form()
    Post.update(where={"id": post_id}, values={"title": form["title"], "body": form["body"]})
    return RedirectResponse("/dashboard")


@app.get("/delete/{id}")
@auth.require
def delete_post(request):
    post_id = int(request.path_params["id"])
    post = Post.get(id=post_id)
    if post and post["author_id"] == request.user["id"]:
        Comment.delete(post_id=post_id)
        Post.delete(id=post_id)
    return RedirectResponse("/dashboard")


if __name__ == "__main__":
    app.serve()
