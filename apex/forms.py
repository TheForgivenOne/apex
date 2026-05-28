import secrets
import re as _re
from typing import Any, Callable, Dict, List, Optional, Type


_validator_registry: Dict[str, Callable] = {}


def validator(name: str = None):
    def decorator(fn):
        key = name or fn.__name__
        _validator_registry[key] = fn
        return fn
    return decorator


class ValidationError:
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
    def __str__(self):
        return self.message


def Required(message: str = "This field is required"):
    def validate(value, field_name):
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationError(field_name, message)
        return None
    return validate


def Email(message: str = "Invalid email address"):
    pattern = _re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    def validate(value, field_name):
        if value and not pattern.match(value):
            return ValidationError(field_name, message)
        return None
    return validate


def MinLength(n: int, message: str = None):
    msg = message or f"Must be at least {n} characters"
    def validate(value, field_name):
        if value and len(value) < n:
            return ValidationError(field_name, msg)
        return None
    return validate


def MaxLength(n: int, message: str = None):
    msg = message or f"Must be at most {n} characters"
    def validate(value, field_name):
        if value and len(value) > n:
            return ValidationError(field_name, msg)
        return None
    return validate


def Match(other_field: str, message: str = None):
    msg = message or f"Must match {other_field}"
    def validate(value, field_name, form_data=None):
        if form_data and value != form_data.get(other_field):
            return ValidationError(field_name, msg)
        return None
    return validate


class Field:
    def __init__(
        self,
        label: str = "",
        validators: List[Callable] = None,
        initial: Any = "",
        placeholder: str = "",
        help_text: str = "",
    ):
        self.label = label
        self.validators = validators or []
        self.initial = initial
        self.placeholder = placeholder
        self.help_text = help_text
        self.value: Any = initial
        self.errors: List[str] = []
        self.name: str = ""

    def validate(self, form_data: Dict[str, Any]) -> List[ValidationError]:
        self.errors = []
        value = form_data.get(self.name, "")
        self.value = value
        errors = []
        for v in self.validators:
            try:
                error = v(value, self.name, form_data) if v.__code__.co_argcount > 2 else v(value, self.name)
            except Exception:
                error = v(value, self.name)
            if error:
                errors.append(error)
                self.errors.append(str(error))
        return errors

    def render(self, **attrs) -> str:
        attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs.items() if v)
        error_html = ""
        if self.errors:
            error_html = f'<div class="form-error">{self.errors[0]}</div>'
        return f'<div class="form-field">{error_html}<label>{self.label}</label>'
        # subclasses define the input

    def input_html(self, **attrs) -> str:
        return ""


class StringField(Field):
    def input_html(self, **attrs) -> str:
        a = f'name="{self.name}" type="text" value="{self.value}" placeholder="{self.placeholder}"'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        return f'<input {a}>'

    def render(self, **attrs) -> str:
        error_html = " ".join(f'<div class="form-error">{e}</div>' for e in self.errors)
        return f'<div class="form-field">{error_html}<label>{self.label}</label>{self.input_html(**attrs)}</div>'


class EmailField(StringField):
    def input_html(self, **attrs) -> str:
        a = f'name="{self.name}" type="email" value="{self.value}" placeholder="{self.placeholder}"'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        return f'<input {a}>'


class PasswordField(Field):
    def input_html(self, **attrs) -> str:
        a = f'name="{self.name}" type="password" placeholder="{self.placeholder}"'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        return f'<input {a}>'

    def render(self, **attrs) -> str:
        error_html = " ".join(f'<div class="form-error">{e}</div>' for e in self.errors)
        return f'<div class="form-field">{error_html}<label>{self.label}</label>{self.input_html(**attrs)}</div>'


class TextAreaField(Field):
    def __init__(self, **kwargs):
        self.rows = kwargs.pop("rows", 5)
        super().__init__(**kwargs)

    def input_html(self, **attrs) -> str:
        a = f'name="{self.name}"'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        return f'<textarea {a} rows="{self.rows}">{self.value}</textarea>'

    def render(self, **attrs) -> str:
        error_html = " ".join(f'<div class="form-error">{e}</div>' for e in self.errors)
        return f'<div class="form-field">{error_html}<label>{self.label}</label>{self.input_html(**attrs)}</div>'


class BooleanField(Field):
    def input_html(self, **attrs) -> str:
        checked = "checked" if self.value else ""
        a = f'name="{self.name}" type="checkbox" {checked}'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        return f'<input {a}>'

    def render(self, **attrs) -> str:
        error_html = " ".join(f'<div class="form-error">{e}</div>' for e in self.errors)
        return f'<div class="form-field">{error_html}<label>{self.input_html(**attrs)} {self.label}</label></div>'


class SelectField(Field):
    def __init__(self, choices: List[tuple] = None, **kwargs):
        self.choices = choices or []
        super().__init__(**kwargs)

    def input_html(self, **attrs) -> str:
        a = f'name="{self.name}"'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        options = "".join(
            f'<option value="{v}" {"selected" if str(v) == str(self.value) else ""}>{l}</option>'
            for v, l in self.choices
        )
        return f'<select {a}>{options}</select>'

    def render(self, **attrs) -> str:
        error_html = " ".join(f'<div class="form-error">{e}</div>' for e in self.errors)
        return f'<div class="form-field">{error_html}<label>{self.label}</label>{self.input_html(**attrs)}</div>'


class FormMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        if name == "Form":
            return cls
        fields = {}
        for key, value in attrs.items():
            if isinstance(value, Field):
                value.name = key
                if not value.label:
                    value.label = key.replace("_", " ").title()
                fields[key] = value
        cls._fields = fields
        return cls


class Form(metaclass=FormMeta):
    _fields: Dict[str, Field] = {}
    _csrf_enabled: bool = True

    def __init__(self, data: Optional[Dict[str, Any]] = None, csrf_token: str = ""):
        self.data = data or {}
        self._errors: Dict[str, List[str]] = {}
        self._csrf_token = csrf_token
        for name, field in self._fields.items():
            field.name = name
            field.value = self.data.get(name, field.initial)
            field.errors = []

    @property
    def errors(self) -> Dict[str, List[str]]:
        return self._errors

    def validate(self) -> bool:
        self._errors = {}
        for name, field in self._fields.items():
            errs = field.validate(self.data)
            if errs:
                self._errors[name] = [str(e) for e in errs]
        if self._csrf_enabled and self._fields:
            expected = self._get_csrf()
            token = self.data.get("_csrf_token", "")
            if not token or token != expected:
                self._errors["_csrf_token"] = ["Invalid CSRF token"]
        return len(self._errors) == 0

    def _get_csrf(self) -> str:
        return self._csrf_token

    def skip_csrf(self):
        self._csrf_enabled = False
        return self

    def render(self, action: str = "", method: str = "POST", **attrs) -> str:
        a = f'action="{action}" method="{method}"'
        for k, v in attrs.items():
            if v:
                a += f' {k}="{v}"'
        fields = "".join(f.render() for f in self._fields.values())
        csrf = ""
        if self._csrf_enabled and self._fields and self._csrf_token:
            csrf = f'<input type="hidden" name="_csrf_token" value="{self._csrf_token}">'
        return f'<form {a}>{csrf}{fields}</form>'

    def render_fields(self) -> str:
        return "".join(f.render() for f in self._fields.values())


def generate_csrf() -> str:
    return secrets.token_hex(32)
