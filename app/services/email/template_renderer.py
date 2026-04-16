"""
Email template renderer — renders Jinja2 HTML and plain text email templates.

Templates live in app/services/email/templates/ and use Jinja2 inheritance:
- base.html: shared layout (DOCTYPE, wrapper div, footer)
- Child templates: {% extends "base.html" %} {% block content %}...{% endblock %}

Plain text: .txt variant loaded alongside .html. Falls back to HTML-stripped version.
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _strip_html(html: str) -> str:
    """Basic HTML to plain text conversion."""
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<li[^>]*>", "- ", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_template(base_name: str, ext: str, locale: str):
    """Try locale-specific template first (e.g. name.es.html), fall back to default (name.html)."""
    if locale and locale != "en":
        try:
            return _env.get_template(f"{base_name}.{locale}.{ext}")
        except Exception:
            pass
    return _env.get_template(f"{base_name}.{ext}")


def render_email(template_name: str, locale: str = "en", **context) -> tuple[str, str]:
    """
    Render an email template with locale support.

    Looks for locale-specific files first (e.g. ``onboarding/need_help.es.html``),
    then falls back to the default English file (``onboarding/need_help.html``).

    Args:
        template_name: Path relative to templates dir, without extension (e.g. "onboarding/need_help")
        locale: Locale code ("en", "es", "pt")
        **context: Template variables

    Returns:
        (text_body, html_body) tuple
    """
    html_template = _get_template(template_name, "html", locale)
    html_body = html_template.render(locale=locale, **context)

    # Try loading a dedicated .txt template; fall back to stripping HTML
    try:
        txt_template = _get_template(template_name, "txt", locale)
        text_body = txt_template.render(locale=locale, **context)
    except Exception:
        text_body = _strip_html(html_body)

    return text_body, html_body
