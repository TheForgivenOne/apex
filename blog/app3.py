from apex import *
from apex.forms import Form, StringField, TextAreaField, EmailField, PasswordField, Required, Email, MinLength, generate_csrf

app = Apex(db_path="/tmp/apex3.db")
setup_templates(["templates"])

# --- Init DB tables for auth + blog models ---
class Post(Model):
    title: str
    body: str
    author_id: int

class Comment(Model):
    post_id: int
    author: str
    body: str

# Manually create tables for auth models too
from apex.auth import User, Session
User.create_table()
Session.create_table()


# --- Forms ---
class PostForm(Form):
    title = StringField(validators=[Required()])
    body = TextAreaField(validators=[Required()])

class RegisterForm(Form):
    username = StringField(validators=[Required(), MinLength(3)])
    email = EmailField(validators=[Required(), Email()])
    password = PasswordField(validators=[Required(), MinLength(6)])

class LoginForm(Form):
    username = StringField(validators=[Required()])
    password = PasswordField(validators=[Required()])


# --- Auth helpers ---
def get_user(request):
    token = ""
    if "session=" in request.headers.get("cookie", ""):
        token = request.headers["cookie"].split("session=")[-1].split(";")[0]
    if token:
        sess = Session.get(token=token)
        if sess:
            return User.get(id=sess["user_id"])
    return None

def require(handler):
    import inspect as _i
    if _i.iscoroutinefunction(handler):
        async def wrapper(req, *a, **kw):
            user = get_user(req)
            if not user:
                return RedirectResponse("/login")
            req.user = user
            return await handler(req, *a, **kw)
        return wrapper
    def wrapper(req, *a, **kw):
        user = get_user(req)
        if not user:
            return RedirectResponse("/login")
        req.user = user
        return handler(req, *a, **kw)
    return wrapper


# --- Routes ---
@app.get("/login")
def login_page(request):
    return render_template("form_page.html",
        title="Login", action="/login", form=LoginForm().render(),
        submit_text="Login",
        extra_link='Don\'t have an account? <a href="/register">Register</a>')


@app.post("/login")
async def login_action(request):
    data = await request.form()
    form = LoginForm(data).skip_csrf()
    if form.validate():
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        found = User.get(username=username)
        if found and auth.verify_password(password, found["password_hash"]):
            token = auth._create_token()
            Session.create(user_id=found["id"], token=token, expires_at="2099-01-01")
            resp = RedirectResponse("/dashboard")
            resp.set_cookie("session", token, max_age=86400 * 7, path="/")
            flash.flash(request, f"Welcome back, {username}!", "success")
            return resp
        form._errors["username"] = ["Invalid username or password"]
    return render_template("form_page.html",
        title="Login", action="/login", form=form.render(),
        submit_text="Login",
        extra_link='Don\'t have an account? <a href="/register">Register</a>')


@app.get("/register")
def register_page(request):
    return render_template("form_page.html",
        title="Register", action="/register", form=RegisterForm().render(),
        submit_text="Register",
        extra_link='Already have an account? <a href="/login">Login</a>')


@app.post("/register")
async def register_action(request):
    data = await request.form()
    form = RegisterForm(data).skip_csrf()
    if form.validate():
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "").strip()
        if User.get(username=username):
            form._errors["username"] = ["Username already taken"]
        elif User.get(email=email):
            form._errors["email"] = ["Email already registered"]
        else:
            User.create(username=username, email=email, password_hash=auth.hash_password(password))
            flash.flash(request, "Registered! Please log in.", "success")
            return RedirectResponse("/login")
    return render_template("form_page.html",
        title="Register", action="/register", form=form.render(),
        submit_text="Register",
        extra_link='Already have an account? <a href="/login">Login</a>')


@app.get("/logout")
def logout(request):
    token = ""
    if "session=" in request.headers.get("cookie", ""):
        token = request.headers["cookie"].split("session=")[-1].split(";")[0]
    if token:
        Session.delete(token=token)
    resp = RedirectResponse("/")
    resp.set_cookie("session", "", max_age=0, path="/")
    return resp


# --- Blog routes ---
@app.get("/")
def home(request):
    user = get_user(request)
    posts = Post.raw("SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id ORDER BY p.created_at DESC")
    for p in posts:
        p["excerpt"] = p["body"][:200] + ("..." if len(p["body"]) > 200 else "")
    flashes = flash.get_flashed_messages(request)
    flash_html = "".join(f'<div class="flash flash-{c}">{m}</div>' for c, m in flashes)
    return render_template("home.html", posts=posts, user=user, flashes=flash_html)


@app.get("/post/{id}")
def view_post(request):
    user = get_user(request)
    post_id = int(request.path_params["id"])
    rows = Post.raw("SELECT p.*, u.username FROM posts p JOIN users u ON p.author_id = u.id WHERE p.id=?", [post_id])
    if not rows:
        return HTMLResponse("404 Not Found", status=404)
    post = rows[0]
    comments = Comment.filter(post_id=post_id)
    return render_template("post.html", post=post, comments=comments, user=user)


@app.post("/comment/{id}")
async def add_comment(request):
    post_id = int(request.path_params["id"])
    form = await request.form()
    Comment.create(post_id=post_id, author=form.get("author", "").strip(), body=form.get("body", "").strip())
    c = Comment.filter(post_id=post_id)[-1]
    return f'<div class="comment"><strong>{c["author"]}</strong><span class="meta">{c["created_at"]}</span><p>{c["body"]}</p></div>'


@app.get("/dashboard")
@require
def dashboard(request):
    user = request.user
    posts = Post.filter(author_id=user["id"])
    return render_template("dashboard.html", user=user, posts=posts)


@app.get("/new")
@require
def new_post_page(request):
    return render_template("new_post.html", user=request.user)


@app.post("/new")
@require
async def create_post(request):
    form = await request.form()
    Post.create(title=form.get("title", "").strip(), body=form.get("body", "").strip(), author_id=request.user["id"])
    flash.flash(request, "Post published!", "success")
    return RedirectResponse("/dashboard")


@app.get("/edit/{id}")
@require
def edit_post_page(request):
    post = Post.get(id=int(request.path_params["id"]))
    if not post or post["author_id"] != request.user["id"]:
        flash.flash(request, "You can only edit your own posts.", "error")
        return RedirectResponse("/dashboard")
    return render_template("edit_post.html", user=request.user, post=post)


@app.post("/edit/{id}")
@require
async def update_post(request):
    post_id = int(request.path_params["id"])
    form = await request.form()
    Post.update(where={"id": post_id}, values={"title": form.get("title"), "body": form.get("body")})
    flash.flash(request, "Post updated!", "success")
    return RedirectResponse("/dashboard")


@app.get("/delete/{id}")
@require
def delete_post(request):
    post_id = int(request.path_params["id"])
    post = Post.get(id=post_id)
    if post and post["author_id"] == request.user["id"]:
        Comment.delete(post_id=post_id)
        Post.delete(id=post_id)
        flash.flash(request, "Post deleted.", "info")
    return RedirectResponse("/dashboard")


if __name__ == "__main__":
    app.serve()
