import re
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from html import escape


class TemplateError(Exception):
    pass


class Context:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.blocks: Dict[str, str] = {}

    def resolve(self, expr: str) -> Any:
        parts = expr.split(".")
        val = self.data
        for p in parts:
            p = p.strip()
            bracket_idx = p.find("[")
            if bracket_idx != -1:
                var_part = p[:bracket_idx]
                if var_part:
                    if isinstance(val, dict):
                        val = val.get(var_part)
                    elif isinstance(val, (list, tuple)):
                        try:
                            val = val[int(var_part)]
                        except (IndexError, ValueError):
                            return ""
                    else:
                        try:
                            val = getattr(val, var_part, "")
                        except Exception:
                            return ""
                rest = p[bracket_idx:]
                if rest:
                    val = self._apply_slice_or_index(val, rest)
            else:
                if isinstance(val, dict):
                    val = val.get(p, "")
                elif isinstance(val, (list, tuple)) and p.isdigit():
                    try:
                        val = val[int(p)]
                    except (IndexError, ValueError):
                        return ""
                else:
                    try:
                        val = getattr(val, p, "")
                    except Exception:
                        return ""
        return val

    def _apply_slice_or_index(self, val: Any, expr: str) -> Any:
        match = re.match(r'^\[(-?\d+)?:(-?\d+)?\]$', expr)
        if match:
            start = int(match.group(1)) if match.group(1) is not None else None
            end = int(match.group(2)) if match.group(2) is not None else None
            try:
                return val[start:end]
            except Exception:
                return ""
        match = re.match(r'^\[(-?\d+)\]$', expr)
        if match:
            idx = int(match.group(1))
            try:
                return val[idx]
            except (IndexError, KeyError, TypeError):
                return ""
        return val

    def get(self, key: str, default: Any = "") -> str:
        key = key.strip()
        parts = key.split("|")
        expr = parts[0].strip()
        filter_names = [f.strip() for f in parts[1:]]
        val = self._eval_expr(expr)
        for fn in filter_names:
            val = self._apply_filter(val, fn)
        return val

    def _eval_expr(self, expr: str) -> Any:
        if expr.startswith("not "):
            return not self._eval_expr(expr[4:].strip())
        parts = re.split(r'\s+(and|or)\s+', expr, maxsplit=1)
        if len(parts) == 3:
            left, op, right = parts[0].strip(), parts[1].strip(), parts[2].strip()
            lv = self._eval_expr(left)
            rv = self._eval_expr(right)
            if op == "and":
                return lv and rv
            elif op == "or":
                return lv or rv
        return self.resolve(expr)

    def get_bool(self, expr: str) -> bool:
        return bool(self._eval_expr(expr))

    def _apply_filter(self, val: Any, name: str) -> Any:
        if "(" in name and name.endswith(")"):
            paren_idx = name.index("(")
            fn = name[:paren_idx]
            args_str = name[paren_idx+1:-1]
            args = _parse_filter_args(args_str)
        else:
            fn = name
            args = []
        filter_fn = BUILTIN_FILTERS.get(fn)
        if filter_fn:
            return filter_fn(val, *args)
        return val


def _parse_filter_args(s: str) -> list:
    args = []
    current = []
    in_quote = False
    quote_char = None
    for c in s:
        if in_quote:
            if c == quote_char:
                in_quote = False
            else:
                current.append(c)
        elif c in ("'", '"'):
            in_quote = True
            quote_char = c
        elif c == ",":
            args.append("".join(current).strip())
            current = []
        else:
            current.append(c)
    rest = "".join(current)
    if rest:
        args.append(rest)
    return args

    def get_bool(self, expr: str) -> bool:
        return bool(self._eval_expr(expr))


BUILTIN_FILTERS: Dict[str, Callable] = {}

def register_filter(name: str, fn: Callable):
    BUILTIN_FILTERS[name] = fn

register_filter("upper", lambda v: str(v).upper())
register_filter("lower", lambda v: str(v).lower())
register_filter("capitalize", lambda v: str(v).capitalize())
register_filter("title", lambda v: str(v).title())
register_filter("trim", lambda v: str(v).strip())
register_filter("length", lambda v: len(v) if hasattr(v, "__len__") else len(str(v)))
register_filter("urlencode", lambda v: __import__("urllib.parse").parse.quote(str(v)))
register_filter("safe", lambda v: v if isinstance(v, str) else str(v))
register_filter("int", lambda v: int(v) if v else 0)

def _join_filter(v, sep=", "):
    if isinstance(v, (list, tuple)):
        return sep.join(str(x) for x in v)
    return str(v)

def _default_filter(v, default=""):
    return v if v else default

def _truncate_filter(v, length="255", suffix="..."):
    try:
        l = int(length)
    except ValueError:
        l = 255
    if hasattr(v, "__len__") and len(v) > l:
        return str(v)[:l] + str(suffix)
    return str(v) if v else ""

register_filter("join", _join_filter)
register_filter("default", _default_filter)
register_filter("truncate", _truncate_filter)


class Template:
    def __init__(self, source: str, name: str = "", loader: "TemplateLoader" = None):
        self.source = source
        self.name = name
        self.loader = loader
        self._parsed: Optional[List[tuple]] = None

    def parse(self):
        if self._parsed:
            return self._parsed
        tokens = []
        i = 0
        while i < len(self.source):
            if self.source[i:i+4] == "{{! ":
                end = self.source.find(" }}", i)
                if end == -1:
                    end = self.source.find("}}", i)
                expr = self.source[i+4:end].strip()
                tokens.append(("raw", expr))
                i = end + (2 if self.source[end:end+2] == "}}" else 3)
            elif self.source[i:i+2] == "{{":
                end = self.source.find("}}", i)
                if end == -1:
                    tokens.append(("text", self.source[i:]))
                    break
                expr = self.source[i+2:end].strip()
                has_filters = "|" in expr
                tokens.append(("expr_raw" if has_filters else "expr", expr))
                i = end + 2
            elif self.source[i:i+2] == "{%":
                end = self.source.find("%}", i)
                if end == -1:
                    tokens.append(("text", self.source[i:]))
                    break
                tag = self.source[i+2:end].strip()
                tokens.append(("tag", tag))
                i = end + 2
            else:
                j = i + 1
                while j < len(self.source):
                    if self.source[j:j+2] in ("{{", "{%"):
                        break
                    j += 1
                tokens.append(("text", self.source[i:j]))
                i = j
        self._parsed = tokens
        return tokens

    def render(self, **context) -> str:
        ctx = Context(context)
        result = self._render_tokens(self.parse(), ctx)
        return result

    def render_with_blocks(self, context: Dict, blocks: Dict) -> str:
        ctx = Context(context)
        ctx.blocks = blocks
        result = self._render_tokens(self.parse(), ctx)
        return result

    def _render_tokens(self, tokens: List[tuple], ctx: Context) -> str:
        result = []
        i = 0
        while i < len(tokens):
            ttype, value = tokens[i]
            if ttype == "text":
                result.append(value)
            elif ttype == "expr":
                result.append(escape(str(ctx.get(value, ""))))
            elif ttype == "expr_raw":
                result.append(str(ctx.get(value, "")))
            elif ttype == "raw":
                val = ctx.get(value, "")
                result.append(str(val))
            elif ttype == "tag":
                if value.startswith("include "):
                    path = value[8:].strip().strip("\"'")
                    result.append(self._include(path, ctx))
                elif value.startswith("extends "):
                    path = value[8:].strip().strip("\"'")
                    inner_tokens = tokens[i+1:]
                    result.append(self._extends(path, inner_tokens, ctx))
                    i = len(tokens) - 1
                elif value.startswith("block "):
                    name = value[6:].strip()
                    end = self._find_end_tag(tokens, i, f"endblock {name}", "endblock")
                    if name in ctx.blocks:
                        result.append(ctx.blocks[name])
                    else:
                        block_content = self._render_tokens(tokens[i+1:end], ctx)
                        ctx.blocks[name] = block_content
                        result.append(block_content)
                    i = end
                    continue
                elif value.startswith("for "):
                    parts = value[4:].split(" in ")
                    var = parts[0].strip()
                    iterable_name = parts[1].strip() if len(parts) > 1 else ""
                    end = self._find_end_tag(tokens, i, "endfor")
                    inner = tokens[i+1:end]
                    items = ctx.get(iterable_name, [])
                    for item in items:
                        ctx.data[var] = item
                        result.append(self._render_tokens(inner, ctx))
                    i = end
                elif value.startswith("if "):
                    cond = value[3:].strip()
                    endif = self._find_endif(tokens, i)
                    else_idx = self._find_else(tokens, i, endif)
                    if ctx.get_bool(cond):
                        result.append(self._render_tokens(tokens[i+1:else_idx or endif], ctx))
                    elif else_idx is not None:
                        result.append(self._render_tokens(tokens[else_idx+1:endif], ctx))
                    i = endif
                elif value == "endif" or value == "endfor" or value.startswith("endblock"):
                    pass
            i += 1
        return "".join(result)

    def _include(self, path: str, ctx: Context) -> str:
        if self.loader:
            tpl = self.loader.load(path)
            if tpl:
                return tpl.render(**ctx.data)
        return f"<!-- missing template: {path} -->"

    def _extends(self, path: str, inner_tokens: List[tuple], ctx: Context) -> str:
        if self.loader:
            self._render_tokens(inner_tokens, ctx)
            tpl = self.loader.load(path)
            if tpl:
                return tpl.render_with_blocks(ctx.data, ctx.blocks)
        return f"<!-- missing layout: {path} -->"

    def _find_end_tag(self, tokens: List[tuple], start: int, *names) -> int:
        depth = 1
        for i in range(start + 1, len(tokens)):
            if tokens[i][0] == "tag":
                tag = tokens[i][1]
                if any(tag.startswith(n.split()[0]) for n in names if n):
                    for n in (names or ("end",)):
                        if tag.startswith(n):
                            depth -= 1
                            if depth == 0:
                                return i
                elif tag.startswith("if ") or tag.startswith("for ") or tag.startswith("block "):
                    depth += 1
        return len(tokens) - 1

    def _find_else(self, tokens: List[tuple], start: int, endif: int):
        depth = 1
        for j in range(start + 1, endif):
            if tokens[j][0] != "tag":
                continue
            tag = tokens[j][1]
            if tag.startswith("if "):
                depth += 1
            elif tag == "endif":
                depth -= 1
            elif tag.startswith("else") and depth == 1:
                return j
        return None

    def _find_endif(self, tokens: List[tuple], start: int) -> int:
        depth = 1
        for i in range(start + 1, len(tokens)):
            if tokens[i][0] == "tag":
                tag = tokens[i][1]
                if tag.startswith("if ") or tag.startswith("for ") or tag.startswith("block "):
                    depth += 1
                elif tag == "endif":
                    depth -= 1
                    if depth == 0:
                        return i
        return len(tokens) - 1


class TemplateLoader:
    def __init__(self, directories: List[str]):
        self.dirs = [Path(d).resolve() for d in directories]
        self._cache: Dict[str, Template] = {}

    def load(self, name: str) -> Optional[Template]:
        if name in self._cache:
            return self._cache[name]
        for d in self.dirs:
            path = d / name
            if path.exists():
                source = path.read_text(encoding="utf-8")
                tpl = Template(source, name=str(path), loader=self)
                self._cache[name] = tpl
                return tpl
        for d in self.dirs:
            for ext in ("", ".html"):
                path = d / (name + ext)
                if path.exists():
                    source = path.read_text(encoding="utf-8")
                    tpl = Template(source, name=str(path), loader=self)
                    self._cache[name] = tpl
                    return tpl
        return None

    def clear_cache(self):
        self._cache.clear()

    def render(self, name: str, **context) -> str:
        tpl = self.load(name)
        if tpl:
            return tpl.render(**context)
        return f"<!-- template not found: {name} -->"


_renderer: Optional[TemplateLoader] = None


def setup(directories: List[str]):
    global _renderer
    _renderer = TemplateLoader(directories)


def render(name: str, **context) -> str:
    if _renderer is None:
        return f"<!-- template engine not configured -->"
    return _renderer.render(name, **context)
