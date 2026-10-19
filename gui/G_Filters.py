"""Template filters, loaded on every page through settings.py (TEMPLATES -> OPTIONS -> builtins)."""
import os
import re
from datetime import datetime

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

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
    """Show a stored mobile number the way the forms type it: '09171234567' becomes '0917 123 4567'. Anything else is
    shown as it is."""
    text = str(value or "")
    if len(text) == 11 and text.isdigit():
        return f"{text[:4]} {text[4:7]} {text[7:]}"
    return value


@register.filter
def mobile_hidden(value):
    """A mobile number with the middle hidden, for the printed ID: '09171234567' becomes '0917 ••• 4567'."""
    text = str(value or "")
    if len(text) == 11 and text.isdigit():
        return f"{text[:4]} \u2022\u2022\u2022 {text[7:]}"
    return value


@register.filter
def ago(when):
    """Say a moment the way people do: 'just now', '5 min ago', '3 h ago', 'yesterday', or the date for older ones."""
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


@register.simple_tag
def greeting():
    """'Good morning', 'Good afternoon' or 'Good evening', based on the server's clock."""
    hour = datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"


@register.filter
def first_name(name):
    """The first word of a name, for friendly sentences: 'Juan Dela Cruz' becomes 'Juan'."""
    words = str(name).split()
    return words[0] if words else ""


@register.filter
def drug(item):
    """The drug in a medication such as 'Amlodipine 5 mg daily': everything before the first number ('Amlodipine')."""
    found = re.match(r"^(.*?)[\s,]+(\d.*)$", str(item))
    return found.group(1) if found else str(item)


@register.filter
def dose(item):
    """The dose in a medication such as 'Amlodipine 5 mg daily': from the first number on ('5 mg daily'), or nothing."""
    found = re.match(r"^(.*?)[\s,]+(\d.*)$", str(item))
    return found.group(2) if found else ""


@register.filter
def pronoun(patient, form):
    """The right small word for a patient, from the sex on their record: pronoun:"he" gives he or she, "his" gives his or
    her, "him" gives him or her. Anything else on file gives the neutral they, their, them."""
    sex = str(getattr(patient, "sex", "")).lower()
    words = {"he": ("he", "she", "they"), "his": ("his", "her", "their"), "him": ("him", "her", "them")}[form]
    return words[0] if sex == "male" else words[1] if sex == "female" else words[2]


@register.filter
def last_name(name):
    """The last word of a name, for the pop-up that asks about a doctor: 'Antonio Santos' becomes 'Santos'."""
    words = str(name).split()
    return words[-1] if words else ""


@register.filter
def day(moment):
    """Only the day, for a list line: 'today', 'yesterday' or the full date, 'Oct 15, 2026'."""
    if not isinstance(moment, datetime):
        return moment
    days = (datetime.now().date() - moment.date()).days
    if days in (0, 1):
        return "today" if days == 0 else "yesterday"
    return f"{moment.strftime('%b')} {moment.day}, {moment.year}"


@register.filter
def when(moment, style=""):
    """A moment for a list row: 'Today, 09:12', 'Yesterday, 14:40' or the full date and time, 'Oct 15, 2026, 14:40'.
    With style "inline" (for the middle of a sentence) the day words are lower case: 'today, 09:12'.
    With style "date" an older moment is only the full date, 'Oct 15, 2026'."""
    if not isinstance(moment, datetime):
        return moment
    days = (datetime.now().date() - moment.date()).days
    clock = moment.strftime("%H:%M")
    if days in (0, 1):
        word = "Today" if days == 0 else "Yesterday"
        return f"{word.lower() if style == 'inline' else word}, {clock}"
    full = f"{moment.strftime('%b')} {moment.day}, {moment.year}"
    return full if style == "date" else f"{full}, {clock}"
