"""Small template helpers for the pages: {% icon "name" %}, {% logo %}, and the initials / tint filters.
Loaded on every page through settings.py (TEMPLATES -> OPTIONS -> builtins)."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Each icon is a few SVG lines on a 24 x 24 grid (style of the free Lucide icon set).
ICONS = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
    "file": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "steth": '<path d="M5 3H4v6a5 5 0 0 0 10 0V3h-1"/><path d="M9 14v1a5 5 0 0 0 10 0v-2"/><circle cx="19" cy="11" r="2"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="M12 8v4M12 16h.01"/>',
    "shieldok": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "pulse": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "pill": '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>',
    "drop": '<path d="M12 2.7s-7 7.3-7 12.3a7 7 0 0 0 14 0c0-5-7-12.3-7-12.3z"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "cal": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "hosp": '<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M12 8v5M9.5 10.5h5"/><path d="M10 21v-4h4v4"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4.1a4 4 0 0 1 0 7.8M22 21a7 7 0 0 0-4-6.3"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "key": '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.3-9.3M17 6l3 3M15 8l2 2"/>',
    "chev": '<path d="m9 18 6-6-6-6"/>',
}

LOGO = '<path d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z"/>'


@register.simple_tag
def icon(name, size=""):
    """Return the SVG for one icon. size can be "sm" (15px) or "lg" (22px)."""
    return mark_safe(f'<svg class="i {size}" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>')


@register.simple_tag
def logo():
    """The white medical cross used in the MedScan logo."""
    return mark_safe(f'<svg class="logo-cross" viewBox="0 0 24 24" aria-hidden="true">{LOGO}</svg>')


@register.filter
def initials(name):
    """'Juan Dela Cruz' -> 'JC'. Used inside the round avatars."""
    words = str(name).split()
    return (words[0][0] + words[-1][0]) if len(words) > 1 else str(name)[:2]


@register.filter
def tint(user_id):
    """Pick one of four avatar colours from the ID, so the same person always gets the same colour."""
    return ["", "c1", "c2", "c3"][int(user_id) % 4]
