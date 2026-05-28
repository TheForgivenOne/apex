import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from apex.template import Template, Context, BUILTIN_FILTERS
from apex.routing import Router, Route, FileSystemRouter
from apex.db import Model, Database, set_db_path, get_db, init_db, Field, clear_model_registry
from apex.forms import (
    Form, StringField, EmailField, PasswordField, TextAreaField,
    BooleanField, SelectField, Required, Email, MinLength, MaxLength, Match,
)
from apex.flash import flash, get_flashed_messages, render_flashed
from apex.auth import hash_password, verify_password, _create_token


# ===== Fixtures =====

@pytest.fixture(autouse=True)
def clean_db():
    clear_model_registry()
    set_db_path(":memory:")
    db = get_db()
    db.connect()
    yield
    db.close()


# ===== Template Engine Tests =====

class TestTemplateBasics:
    def test_text_only(self):
        t = Template("hello world")
        assert t.render() == "hello world"

    def test_variable_interpolation(self):
        t = Template("<h1>{{ title }}</h1>")
        assert t.render(title="Hello") == "<h1>Hello</h1>"

    def test_raw_output(self):
        t = Template("{{! content }}")
        assert t.render(content="<b>bold</b>") == "<b>bold</b>"

    def test_auto_escape(self):
        t = Template("{{ content }}")
        assert t.render(content='<script>alert(1)</script>') == '&lt;script&gt;alert(1)&lt;/script&gt;'

    def test_dot_notation_dict(self):
        t = Template("{{ post.title }}")
        assert t.render(post={"title": "My Post"}) == "My Post"

    def test_dot_notation_attr(self):
        class Obj:
            name = "test"
        t = Template("{{ obj.name }}")
        assert t.render(obj=Obj()) == "test"

    def test_missing_variable(self):
        t = Template("{{ missing }}")
        assert t.render() == ""


class TestTemplateFilters:
    def test_upper(self):
        t = Template("{{ name|upper }}")
        assert t.render(name="hello") == "HELLO"

    def test_lower(self):
        t = Template("{{ name|lower }}")
        assert t.render(name="HELLO") == "hello"

    def test_capitalize(self):
        t = Template("{{ name|capitalize }}")
        assert t.render(name="hello") == "Hello"

    def test_title(self):
        t = Template("{{ name|title }}")
        assert t.render(name="hello world") == "Hello World"

    def test_trim(self):
        t = Template("{{ name|trim }}")
        assert t.render(name="  hello  ") == "hello"

    def test_length(self):
        t = Template("{{ name|length }}")
        assert t.render(name="hello") == "5"
        assert t.render(name=[1, 2, 3]) == "3"

    def test_truncate(self):
        t = Template("{{ text|truncate(10) }}")
        assert t.render(text="hello world this is long") == "hello worl..."

    def test_truncate_custom(self):
        t = Template('{{ text|truncate(5,"..") }}')
        assert t.render(text="hello world") == "hello.."

    def test_join(self):
        t = Template('{{ items|join(", ") }}')
        assert t.render(items=["a", "b", "c"]) == "a, b, c"

    def test_default(self):
        t = Template('{{ val|default("fallback") }}')
        assert t.render(val="") == "fallback"
        assert t.render(val="real") == "real"

    def test_chained_filters(self):
        t = Template("{{ text|trim|upper }}")
        assert t.render(text="  hello  ") == "HELLO"

    def test_dot_and_filter(self):
        t = Template("{{ post.title|upper }}")
        assert t.render(post={"title": "hello"}) == "HELLO"


class TestTemplateSlicing:
    def test_string_slice(self):
        t = Template("{{ text[:5] }}")
        assert t.render(text="hello world") == "hello"

    def test_string_slice_start_end(self):
        t = Template("{{ text[6:11] }}")
        assert t.render(text="hello world") == "world"

    def test_string_slice_all(self):
        t = Template("{{ text[:] }}")
        assert t.render(text="hello") == "hello"

    def test_list_index(self):
        t = Template("{{ items[0] }}")
        assert t.render(items=["a", "b"]) == "a"

    def test_slice_with_filter(self):
        t = Template("{{ text[:5]|upper }}")
        assert t.render(text="hello world") == "HELLO"

    def test_dict_dot_with_slice(self):
        t = Template("{{ post.body[:10] }}")
        assert t.render(post={"body": "hello world"}) == "hello worl"


class TestTemplateBlocks:
    def test_extends_and_block(self):
        loader = _MockLoader({
            "layout.html": "<title>{% block title %}Default{% endblock %}</title>",
        })
        source = '{% extends "layout.html" %}{% block title %}My Page{% endblock %}'
        t = Template(source, loader=loader)
        result = t.render()
        assert result == "<title>My Page</title>", f"got: {result}"

    def test_block_default_content(self):
        loader = _MockLoader({
            "layout.html": "<body>{% block content %}Empty{% endblock %}</body>",
        })
        source = '{% extends "layout.html" %}{% block content %}Hello{% endblock %}'
        t = Template(source, loader=loader)
        assert t.render() == "<body>Hello</body>"

    def test_multiple_blocks(self):
        loader = _MockLoader({
            "layout.html": "<h1>{% block h1 %}A{% endblock %}</h1><p>{% block p %}B{% endblock %}</p>",
        })
        source = '{% extends "layout.html" %}{% block h1 %}Big{% endblock %}{% block p %}Small{% endblock %}'
        t = Template(source, loader=loader)
        assert t.render() == "<h1>Big</h1><p>Small</p>"

    def test_block_in_child_reuses_parent_default(self):
        loader = _MockLoader({
            "layout.html": "<div>{% block content %}parent{% endblock %}</div>",
        })
        source = '{% extends "layout.html" %}'
        t = Template(source, loader=loader)
        assert t.render() == "<div>parent</div>"


class TestTemplateForLoop:
    def test_basic_for(self):
        t = Template("{% for item in items %}-{{ item }}-{% endfor %}")
        assert t.render(items=["a", "b"]) == "-a--b-"

    def test_for_with_dicts(self):
        t = Template("{% for p in posts %}{{ p.title }}/{% endfor %}")
        assert t.render(posts=[{"title": "A"}, {"title": "B"}]) == "A/B/"

    def test_empty_for(self):
        t = Template("{% for item in items %}{{ item }}{% endfor %}")
        assert t.render(items=[]) == ""


class TestTemplateIf:
    def test_if_true(self):
        t = Template("{% if show %}yes{% endif %}")
        assert t.render(show=True) == "yes"

    def test_if_false(self):
        t = Template("{% if show %}yes{% endif %}")
        assert t.render(show=False) == ""

    def test_if_else(self):
        t = Template("{% if show %}yes{% else %}no{% endif %}")
        assert t.render(show=True) == "yes"
        assert t.render(show=False) == "no"

    def test_if_or(self):
        t = Template("{% if a or b %}yes{% endif %}")
        assert t.render(a=False, b=True) == "yes"
        assert t.render(a=False, b=False) == ""

    def test_if_and(self):
        t = Template("{% if a and b %}yes{% endif %}")
        assert t.render(a=True, b=True) == "yes"
        assert t.render(a=True, b=False) == ""

    def test_if_not(self):
        t = Template("{% if not hidden %}visible{% endif %}")
        assert t.render(hidden=False) == "visible"
        assert t.render(hidden=True) == ""

    def test_if_nested(self):
        t = Template("{% if outer %}{% if inner %}both{% else %}outer only{% endif %}{% endif %}")
        assert t.render(outer=True, inner=True) == "both"
        assert t.render(outer=True, inner=False) == "outer only"
        assert t.render(outer=False, inner=True) == ""

    def test_if_list_not_empty(self):
        t = Template("{% if items %}has items{% else %}empty{% endif %}")
        assert t.render(items=[1, 2]) == "has items"
        assert t.render(items=[]) == "empty"


class TestTemplateInclude:
    def test_include(self):
        loader = _MockLoader({
            "header.html": "<header>My Site</header>",
        })
        t = Template('{% include "header.html" %}', loader=loader)
        assert t.render() == "<header>My Site</header>"

    def test_missing_include(self):
        loader = _MockLoader({})
        t = Template('{% include "missing.html" %}', loader=loader)
        assert "missing template" in t.render()


class TestTemplateFullPage:
    def test_complex_page(self):
        loader = _MockLoader({
            "layout.html": """<!DOCTYPE html>
<html>
<head><title>{% block title %}Default{% endblock %}</title></head>
<body>
<nav>{% if user %}Logged in{% else %}Guest{% endif %}</nav>
<main>{% block content %}{% endblock %}</main>
</body>
</html>""",
        })
        source = """{% extends "layout.html" %}
{% block title %}{{ page_title|upper }}{% endblock %}
{% block content %}
<h1>Posts</h1>
{% for post in posts %}
<div>{{ post.title }} by {{ post.author }}</div>
{% endfor %}
{% if not posts %}
<p>No posts yet</p>
{% endif %}
{% endblock %}"""
        t = Template(source, loader=loader)
        result = t.render(page_title="my blog", user=True,
                          posts=[{"title": "Hello", "author": "Alice"}])
        assert "MY BLOG" in result
        assert "Hello by Alice" in result
        assert "Logged in" in result
        assert "No posts yet" not in result

    def test_empty_posts_page(self):
        loader = _MockLoader({"layout.html": "{% block content %}{% endblock %}"})
        source = """{% extends "layout.html" %}
{% block content %}{% for p in posts %}{{ p }}{% endfor %}{% if not posts %}empty{% endif %}{% endblock %}"""
        t = Template(source, loader=loader)
        assert "empty" in t.render(posts=[])


class _MockLoader:
    def __init__(self, templates: dict):
        self._templates = templates

    def load(self, name):
        if name in self._templates:
            return Template(self._templates[name], name=name, loader=self)
        return None


# ===== ORM Tests =====

@pytest.fixture
def db():
    set_db_path(":memory:")
    db = get_db()
    db.connect()
    return db


class TestModelCreation:
    def test_auto_fields(self):
        class TestModel(Model):
            name: str
        init_db()
        assert "id" in TestModel._fields
        assert "created_at" in TestModel._fields
        assert "name" in TestModel._fields

    def test_create_and_get(self):
        class Item(Model):
            name: str
        init_db()
        obj = Item.create(name="test")
        assert obj["id"] == 1
        assert obj["name"] == "test"
        fetched = Item.get(id=1)
        assert fetched["name"] == "test"

    def test_all(self):
        class Item(Model):
            name: str
        init_db()
        Item.create(name="a")
        Item.create(name="b")
        items = Item.all()
        assert len(items) == 2
        assert items[0]["name"] == "a"

    def test_filter(self):
        class Item(Model):
            category: str
        init_db()
        Item.create(category="x")
        Item.create(category="y")
        assert len(Item.filter(category="x")) == 1
        assert len(Item.filter(category="z")) == 0

    def test_update(self):
        class Item(Model):
            name: str
        init_db()
        Item.create(name="old")
        Item.update(where={"id": 1}, values={"name": "new"})
        assert Item.get(id=1)["name"] == "new"

    def test_delete(self):
        class Item(Model):
            name: str
        init_db()
        Item.create(name="temp")
        assert Item.count() == 1
        Item.delete(id=1)
        assert Item.count() == 0

    def test_count(self):
        class Item(Model):
            name: str
        init_db()
        assert Item.count() == 0
        Item.create(name="a")
        assert Item.count() == 1

    def test_raw_sql(self):
        class Item(Model):
            name: str
        init_db()
        Item.create(name="hello")
        rows = Item.raw("SELECT * FROM items WHERE name=?", ["hello"])
        assert len(rows) == 1
        assert rows[0]["name"] == "hello"

    def test_get_nonexistent(self):
        class Item(Model):
            name: str
        init_db()
        assert Item.get(id=999) is None

    def test_custom_tablename(self):
        class CustomItem(Model):
            __tablename__ = "custom_things"
            name: str
        init_db()
        assert CustomItem._tablename == "custom_things"
        CustomItem.create(name="test")
        rows = CustomItem.raw("SELECT * FROM custom_things")
        assert len(rows) == 1


class TestFieldDefinition:
    def test_field_with_default(self):
        class Item(Model):
            name: str
            score: int = 0  # not a Field, just annotation
        assert "score" in Item._fields
        assert Item._fields["score"].sql_type == "INTEGER"


# ===== Router Tests =====

class TestRouter:
    def test_static_route(self):
        router = Router()
        def handler(req): return "ok"
        router.add("/", handler, methods=["GET"])
        result = router.resolve("/", "GET")
        assert result is not None
        assert result[0] is handler

    def test_static_route_wrong_method(self):
        router = Router()
        def handler(req): return "ok"
        router.add("/", handler, methods=["GET"])
        result = router.resolve("/", "POST")
        assert result is None

    def test_dynamic_route(self):
        router = Router()
        def handler(req): return "post"
        router.add("/post/{id}", handler, methods=["GET"])
        result = router.resolve("/post/42", "GET")
        assert result is not None
        h, params = result
        assert h is handler
        assert params == {"id": "42"}

    def test_dynamic_route_no_match(self):
        router = Router()
        def handler(req): return "post"
        router.add("/post/{id}", handler, methods=["GET"])
        result = router.resolve("/other", "GET")
        assert result is None

    def test_multiple_routes(self):
        router = Router()
        def h1(req): return "a"
        def h2(req): return "b"
        router.add("/a", h1)
        router.add("/b", h2)
        assert router.resolve("/a", "GET")[0] is h1
        assert router.resolve("/b", "GET")[0] is h2

    def test_url_for(self):
        router = Router()
        def handler(req): return "ok"
        router.add("/post/{id}", handler, methods=["GET"], name="post")
        url = router.url_for("post", id=5)
        assert url == "/post/5"

    def test_trailing_slash_normalization(self):
        router = Router()
        def handler(req): return "ok"
        router.add("/about", handler)
        result = router.resolve("/about/", "GET")
        assert result is not None

    def test_route_count(self):
        router = Router()
        router.add("/a", lambda r: "a")
        router.add("/b", lambda r: "b")
        assert router.count == 2

    def test_include_router(self):
        parent = Router()
        child = Router()
        child.add("/posts", lambda r: "posts")
        parent.include_router("/api", child)
        assert parent.resolve("/api/posts", "GET") is not None


# ===== Forms Tests =====

class TestFormValidation:
    def test_valid_form(self):
        class F(Form):
            name = StringField(validators=[Required()])
        form = F({"name": "Alice"}).skip_csrf()
        assert form.validate() is True
        assert form.errors == {}

    def test_required_field_missing(self):
        class F(Form):
            name = StringField(validators=[Required()])
        form = F({"name": ""}).skip_csrf()
        assert form.validate() is False
        assert "name" in form.errors

    def test_email_validation(self):
        class F(Form):
            email = EmailField(validators=[Email()])
        form = F({"email": "not-an-email"}).skip_csrf()
        assert form.validate() is False
        assert "email" in form.errors
        form2 = F({"email": "a@b.com"}).skip_csrf()
        assert form2.validate() is True

    def test_min_length(self):
        class F(Form):
            name = StringField(validators=[MinLength(3)])
        form = F({"name": "ab"}).skip_csrf()
        assert form.validate() is False
        form2 = F({"name": "abc"}).skip_csrf()
        assert form2.validate() is True

    def test_max_length(self):
        class F(Form):
            name = StringField(validators=[MaxLength(5)])
        form = F({"name": "toolong"}).skip_csrf()
        assert form.validate() is False
        form2 = F({"name": "abc"}).skip_csrf()
        assert form2.validate() is True

    def test_match(self):
        class F(Form):
            pwd = PasswordField(validators=[Required()])
            confirm = PasswordField(validators=[Match("pwd")])
        form = F({"pwd": "secret", "confirm": "different"}).skip_csrf()
        assert form.validate() is False
        form2 = F({"pwd": "secret", "confirm": "secret"}).skip_csrf()
        assert form2.validate() is True

    def test_multiple_validators(self):
        class F(Form):
            name = StringField(validators=[Required(), MinLength(3), MaxLength(10)])
        form = F({"name": ""}).skip_csrf()
        assert form.validate() is False
        form2 = F({"name": "ab"}).skip_csrf()
        assert form2.validate() is False
        form3 = F({"name": "abc"}).skip_csrf()
        assert form3.validate() is True

    def test_field_render(self):
        class F(Form):
            name = StringField(label="Your Name", placeholder="Enter name")
        form = F().skip_csrf()
        html = form.render_fields()
        assert "Your Name" in html
        assert "Enter name" in html
        assert 'type="text"' in html

    def test_error_render(self):
        field = StringField(label="Name", validators=[Required()])
        field.name = "name"
        field.validate({"name": ""})
        html = field.render()
        assert "form-error" in html
        assert "required" in html.lower()


# ===== Auth Tests =====

class TestAuth:
    def test_hash_and_verify(self):
        pw = "my_secret_password"
        h = hash_password(pw)
        assert verify_password(pw, h) is True
        assert verify_password("wrong", h) is False

    def test_token_creation(self):
        t1 = _create_token()
        t2 = _create_token()
        assert len(t1) == 64  # 32 bytes = 64 hex chars
        assert t1 != t2  # should be unique

    def test_hash_format(self):
        h = hash_password("test")
        assert ":" in h
        salt, digest = h.split(":")
        assert len(salt) == 32  # 16 bytes = 32 hex chars
        assert len(digest) == 64  # 32 bytes = 64 hex chars


# ===== Flash Messages Tests =====

class TestFlash:
    def test_flash_and_get(self):
        class FakeRequest:
            pass
        req = FakeRequest()
        flash(req, "Hello", "success")
        flash(req, "Error occurred", "error")
        msgs = get_flashed_messages(req)
        assert len(msgs) == 2
        assert msgs[0] == ("success", "Hello")
        assert msgs[1] == ("error", "Error occurred")

    def test_flash_clears_after_read(self):
        class FakeRequest:
            pass
        req = FakeRequest()
        flash(req, "once")
        get_flashed_messages(req)
        assert get_flashed_messages(req) == []

    def test_render_flashed(self):
        class FakeRequest:
            pass
        req = FakeRequest()
        flash(req, "Done!", "success")
        html = render_flashed(req)
        assert "Done!" in html
        assert "flash-success" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
