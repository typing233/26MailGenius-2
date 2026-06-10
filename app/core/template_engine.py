import re
from typing import Any

import bleach
from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment

ALLOWED_TAGS = [
    "a", "abbr", "acronym", "address", "b", "blockquote", "br", "center",
    "div", "em", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i",
    "img", "li", "ol", "p", "pre", "span", "strong", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "u", "ul", "sup", "sub",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "style", "dir", "lang"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "border"],
    "font": ["color", "face", "size"],
    "table": ["border", "cellpadding", "cellspacing", "width", "align"],
    "td": ["width", "height", "align", "valign", "colspan", "rowspan", "bgcolor"],
    "th": ["width", "height", "align", "valign", "colspan", "rowspan", "bgcolor"],
}

BLOCKED_PATTERNS = [
    re.compile(r"\{%\s*import\b"),
    re.compile(r"\{%\s*include\b"),
    re.compile(r"\{%\s*from\b"),
    re.compile(r"\{\{\s*config\b"),
    re.compile(r"\{\{\s*self\b"),
    re.compile(r"\{\{\s*request\b"),
    re.compile(r"__\w+__"),
]


def _create_sandbox() -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        autoescape=True,
        keep_trailing_newline=True,
    )
    env.globals = {}
    return env


_sandbox = _create_sandbox()


def validate_template_source(html_source: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(html_source):
            errors.append({"type": "security", "message": f"Blocked pattern detected: {pattern.pattern}"})
    try:
        _sandbox.parse(html_source)
    except TemplateSyntaxError as e:
        errors.append({"type": "syntax", "message": str(e), "line": str(e.lineno or 0)})
    return errors


def extract_variables(html_source: str) -> list[str]:
    env = _create_sandbox()
    try:
        ast = env.parse(html_source)
    except TemplateSyntaxError:
        return []
    from jinja2 import meta
    return sorted(meta.find_undeclared_variables(ast))


def render_template(html_source: str, variables: dict[str, Any]) -> str:
    env = _create_sandbox()
    template = env.from_string(html_source)
    return template.render(**variables)


def sanitize_html(html: str) -> str:
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )


def render_with_sanitize(html_source: str, variables: dict[str, Any]) -> str:
    rendered = render_template(html_source, variables)
    return sanitize_html(rendered)
