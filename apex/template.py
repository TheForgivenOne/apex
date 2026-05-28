import re
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from html import escape


class TemplateError(Exception):
    pass


class Context:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.blocks: Dict[str, str] = {}

    def get(self, key: str, default: Any = "") -> Any:
        key = key.strip()
        if key.startswith("not "):
            val = self.get(key[4:].strip())
            return not val
        parts = key.split(".")
        val = self.data
        for p in parts:
            p = p.strip()
            if isinstance(val, dict):
                val = val.get(p, default)
            elif isinstance(val, (list, tuple)) and p.isdigit():
                try:
                    val = val[int(p)]
                except (IndexError, ValueError):
                    return default
            else:
                try:
                    val = getattr(val, p, default)
                except Exception:
                    return default
        return val


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
                tokens.append(("expr", expr))
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
                    end = self._find_else_or_endif(tokens, i)
                    else_idx = None
                    for j in range(i+1, end):
                        if tokens[j][0] == "tag" and (tokens[j][1].startswith("else") or tokens[j][1] == "endif"):
                            if tokens[j][1].startswith("else"):
                                else_idx = j
                            break
                    if else_idx is None:
                        else_idx = end
                    if ctx.get(cond, False):
                        result.append(self._render_tokens(tokens[i+1:else_idx], ctx))
                    else:
                        result.append(self._render_tokens(tokens[else_idx+1:end], ctx))
                    i = end
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

    def _find_else_or_endif(self, tokens: List[tuple], start: int) -> int:
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
                elif tag.startswith("else") and depth == 1:
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
