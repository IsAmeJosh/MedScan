"""Template filters, loaded on every page through settings.py (TEMPLATES -> OPTIONS -> builtins)."""
from datetime import datetime

from django import template

register = template.Library()


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
