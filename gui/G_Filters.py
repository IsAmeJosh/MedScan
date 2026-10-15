"""Template filters, loaded on every page through settings.py (TEMPLATES -> OPTIONS -> builtins)."""
import os
from datetime import datetime

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def asset(path):
    """The address of a stylesheet or script, with the time the file was last changed on the end
    (/static/css/G_Style.css?v=1760400000). When a file changes its address changes, so a browser never keeps showing
    an old copy, and nobody has to remember to bump a version number."""
    found = finders.find(path)
    stamp = int(os.path.getmtime(found)) if found else 0
    return f"{static(path)}?v={stamp}"


@register.filter
def mobile(value):
    """'09171234567' -> '0917 123 4567', the same spacing the forms type in. Anything else is shown as it is."""
    text = str(value or "")
    if len(text) == 11 and text.isdigit():
        return f"{text[:4]} {text[4:7]} {text[7:]}"
    return value


@register.filter
def ago(when):
    """A moment as people say it: 'just now', '5 min ago', '3 h ago', 'yesterday', or the date for older ones."""
    if not isinstance(when, datetime):
        return when
    seconds = (datetime.now() - when).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    if seconds < 172800:
        return "yesterday"
    return when.strftime("%b %d, %Y").replace(" 0", " ")
