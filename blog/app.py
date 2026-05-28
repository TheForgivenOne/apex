from apex import Apex, HTMLResponse, JSONResponse, RedirectResponse, live, db, auth
from apex.db import Model, Field, init_db

app = Apex()


class Post(Model):
    __tablename__ = "posts"
    id = Field("INTEGER", primary_key=True)
    title = Field("TEXT", nullable=False)
    body = Field("TEXT", nullable=False)
    author_id = Field("INTEGER", nullable=False)
    created_at = Field("TEXT", default="CURRENT_TIMESTAMP")


class Comment(Model):
    __tablename__ = "comments"
    id = Field("INTEGER", primary_key=True)
    post_id = Field("INTEGER", nullable=False)
    author = Field("TEXT", nullable=False)
    body = Field("TEXT", nullable=False)
    created_at = Field("TEXT", default="CURRENT_TIMESTAMP")


db.set_db_path("/tmp/apex_blog.db")
init_db()
auth.init(app)


@app.get("/")
async def home(request):
    user = auth.get_user(request)
    posts = Post.raw("SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id ORDER BY p.created_at DESC")
    items = ""
    for post in posts:
        items += f"""
        <div class="post-card">
            <h2><a href="/post/{post['id']}">{post['title']}</a></h2>
            <p class="meta">by {post['username']} &middot; {post['created_at']}</p>
            <p>{post['body'][:200]}{'...' if len(post['body']) > 200 else ''}</p>
        </div>"""
    if not items:
        items = '<p style="color:#999;text-align:center;padding:2rem;">No posts yet. Be the first!</p>'

    user_bar = ""
    if user:
        user_bar = f"""
        <div style="display:flex;gap:1rem;align-items:center;">
            <span>Hi, <strong>{user['username']}</strong></span>
            <a href="/dashboard" class="btn btn-sm">Dashboard</a>
            <a href="/new" class="btn btn-sm btn-primary">New Post</a>
            <a href="/logout" class="btn btn-sm">Logout</a>
        </div>"""
    else:
        user_bar = """
        <div style="display:flex;gap:1rem;">
            <a href="/login" class="btn btn-sm">Login</a>
            <a href="/register" class="btn btn-sm btn-primary">Register</a>
        </div>"""

    return HTMLResponse(content=LAYOUT.format(
        title="Apex Blog",
        content=f"""
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
            <h1 style="margin:0;">Apex Blog</h1>
            {user_bar}
        </div>
        {items}
        """,
    ))


@app.get("/post/{id}")
async def view_post(request):
    user = auth.get_user(request)
    post_id = int(request.path_params["id"])
    rows = Post.raw("SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id WHERE p.id = ?", [post_id])
    if not rows:
        return HTMLResponse(content=LAYOUT.format(title="Not Found", content="<h1>404</h1><p>Post not found.</p>"))
    post = rows[0]

    comments = Comment.filter(post_id=post_id)
    comments_html = ""
    for c in comments:
        comments_html += f"""
        <div class="comment">
            <strong>{c['author']}</strong>
            <span class="meta">{c['created_at']}</span>
            <p>{c['body']}</p>
        </div>"""
    if not comments_html:
        comments_html = '<p style="color:#999;">No comments yet.</p>'

    return HTMLResponse(content=LAYOUT.format(
        title=post["title"],
        content=f"""
        <p><a href="/" style="color:#0070f3;">&larr; Back to posts</a></p>
        <h1>{post['title']}</h1>
        <p class="meta">by {post['username']} &middot; {post['created_at']}</p>
        <div class="post-body">{post['body']}</div>
        <hr>
        <h3>Comments</h3>
        <div id="comments">{comments_html}</div>
        <div class="card" style="margin-top:1rem;">
            <form hx-post="/post/{post_id}/comment"
                  hx-target="#comments"
                  hx-swap="beforeend"
                  hx-on::after-request="this.reset()">
                <input type="text" name="author" placeholder="Your name" required style="width:200px;margin-bottom:0.5rem;">
                <textarea name="body" placeholder="Write a comment..." required style="width:100%;padding:0.5rem;border:1px solid #ccc;border-radius:6px;min-height:80px;"></textarea>
                <button type="submit" class="btn btn-primary">Post Comment</button>
            </form>
        </div>
        """,
    ))


@app.post("/post/{id}/comment")
async def add_comment(request):
    post_id = int(request.path_params["id"])
    form = await request.form()
    author = form.get("author", "").strip()
    body = form.get("body", "").strip()
    if author and body:
        Comment.create(post_id=post_id, author=author, body=body)
    c = Comment.filter(post_id=post_id)[-1]
    return HTMLResponse(content=f"""
    <div class="comment">
        <strong>{author}</strong>
        <span class="meta">{c['created_at']}</span>
        <p>{body}</p>
    </div>
    """)


@app.get("/dashboard")
@auth.require
async def dashboard(request):
    user = request.user
    posts = Post.filter(author_id=user["id"])
    items = ""
    for p in posts:
        items += f"""
        <div class="post-card" style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <strong><a href="/post/{p['id']}">{p['title']}</a></strong>
                <span class="meta"> {p['created_at']}</span>
            </div>
            <div style="display:flex;gap:0.5rem;">
                <a href="/edit/{p['id']}" class="btn btn-sm">Edit</a>
                <form hx-post="/delete/{p['id']}" hx-target="closest div" hx-swap="outerHTML"
                      onsubmit="return confirm('Delete this post?')">
                    <button type="submit" class="btn btn-sm" style="background:#e00;">Delete</button>
                </form>
            </div>
        </div>"""
    if not items:
        items = '<p style="color:#999;">You haven\'t written any posts yet. <a href="/new">Write your first post!</a></p>'

    return HTMLResponse(content=LAYOUT.format(
        title="Dashboard",
        content=f"""
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
            <h1 style="margin:0;">Dashboard</h1>
            <a href="/new" class="btn btn-primary">New Post</a>
        </div>
        <p class="meta">Welcome back, {user['username']} ({user['email']})</p>
        <h3 style="margin-top:2rem;">Your Posts</h3>
        {items}
        <p style="margin-top:2rem;"><a href="/">&larr; Back to blog</a></p>
        """,
    ))


@app.get("/new")
@auth.require
async def new_post_page(request):
    return HTMLResponse(content=LAYOUT.format(
        title="New Post",
        content=f"""
        <h1>New Post</h1>
        <form method="POST" action="/new">
            <input type="text" name="title" placeholder="Post title" required
                   style="width:100%;padding:0.75rem;border:1px solid #ccc;border-radius:6px;font-size:1.2rem;margin-bottom:1rem;">
            <textarea name="body" placeholder="Write your post here... (supports HTML)" required
                      style="width:100%;padding:0.75rem;border:1px solid #ccc;border-radius:6px;min-height:300px;font-size:1rem;"></textarea>
            <div style="display:flex;gap:1rem;">
                <button type="submit" class="btn btn-primary">Publish</button>
                <a href="/dashboard" class="btn">Cancel</a>
            </div>
        </form>
        """,
    ))


@app.post("/new")
@auth.require
async def new_post_action(request):
    user = request.user
    form = await request.form()
    title = form.get("title", "").strip()
    body = form.get("body", "").strip()
    if title and body:
        Post.create(title=title, body=body, author_id=user["id"])
        return RedirectResponse("/dashboard")
    return RedirectResponse("/new")


@app.get("/edit/{id}")
@auth.require
async def edit_post_page(request):
    user = request.user
    post_id = int(request.path_params["id"])
    post = Post.get(id=post_id)
    if not post or post["author_id"] != user["id"]:
        return HTMLResponse(content=LAYOUT.format(title="Error", content="<h1>403</h1><p>Not your post.</p>"))
    return HTMLResponse(content=LAYOUT.format(
        title="Edit Post",
        content=f"""
        <h1>Edit Post</h1>
        <form method="POST" action="/edit/{post_id}">
            <input type="text" name="title" value="{post['title']}" required
                   style="width:100%;padding:0.75rem;border:1px solid #ccc;border-radius:6px;font-size:1.2rem;margin-bottom:1rem;">
            <textarea name="body" required
                      style="width:100%;padding:0.75rem;border:1px solid #ccc;border-radius:6px;min-height:300px;font-size:1rem;">{post['body']}</textarea>
            <div style="display:flex;gap:1rem;">
                <button type="submit" class="btn btn-primary">Update</button>
                <a href="/dashboard" class="btn">Cancel</a>
            </div>
        </form>
        """,
    ))


@app.post("/edit/{id}")
@auth.require
async def edit_post_action(request):
    user = request.user
    post_id = int(request.path_params["id"])
    post = Post.get(id=post_id)
    if not post or post["author_id"] != user["id"]:
        return RedirectResponse("/dashboard")
    form = await request.form()
    title = form.get("title", "").strip()
    body = form.get("body", "").strip()
    if title and body:
        Post.update(where={"id": post_id}, values={"title": title, "body": body})
    return RedirectResponse("/dashboard")


@app.post("/delete/{id}")
@auth.require
async def delete_post(request):
    user = request.user
    post_id = int(request.path_params["id"])
    post = Post.get(id=post_id)
    if post and post["author_id"] == user["id"]:
        Comment.delete(post_id=post_id)
        Post.delete(id=post_id)
    return HTMLResponse(content="")


@app.get("/favicon.ico")
async def favicon(request):
    return Response(status=204)


LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} - Apex Blog</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
               max-width:800px; margin:0 auto; padding:2rem; color:#333; line-height:1.6; }}
        h1 {{ margin-bottom:1rem; }}
        a {{ color:#0070f3; text-decoration:none; }}
        a:hover {{ text-decoration:underline; }}
        .btn {{ display:inline-block; padding:0.5rem 1rem; border:1px solid #ccc;
                border-radius:6px; background:white; color:#333; cursor:pointer;
                font-size:0.9rem; text-decoration:none !important; }}
        .btn:hover {{ background:#f0f0f0; }}
        .btn-primary {{ background:#0070f3; color:white; border-color:#0070f3; }}
        .btn-primary:hover {{ background:#005bb5; }}
        .btn-sm {{ padding:0.3rem 0.7rem; font-size:0.8rem; }}
        .post-card {{ background:#f9f9f9; padding:1.5rem; border-radius:8px; margin-bottom:1rem; }}
        .post-card h2 {{ margin-bottom:0.25rem; }}
        .post-card h2 a {{ color:#111; }}
        .meta {{ color:#888; font-size:0.85rem; margin-bottom:0.5rem; }}
        .post-body {{ margin:1.5rem 0; line-height:1.8; }}
        .comment {{ padding:0.75rem; border-bottom:1px solid #eee; }}
        .comment:last-child {{ border-bottom:none; }}
        .card {{ background:#f5f5f5; padding:1.5rem; border-radius:8px; }}
        input, textarea {{ font-family:inherit; }}
        hr {{ border:none; border-top:1px solid #eee; margin:1.5rem 0; }}
    </style>
</head>
<body>
    <nav style="display:flex;gap:1rem;margin-bottom:2rem;padding-bottom:1rem;border-bottom:1px solid #eee;">
        <a href="/" style="font-weight:bold;color:#111;">Apex Blog</a>
        <span style="flex:1;"></span>
    </nav>
    <main>{content}</main>
</body>
</html>"""


if __name__ == "__main__":
    app.serve()
