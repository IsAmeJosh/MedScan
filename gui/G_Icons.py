"""Small helpers for the templates: {% icon "name" %} draws an icon, {% logo %} draws the logo mark, and the initials
and tint filters make the round avatars. They are loaded on every page through settings.py (TEMPLATES -> OPTIONS ->
builtins), so a template never needs its own {% load %}."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Each icon is a few SVG lines on a 24 x 24 grid. These are the icons of the design (design/).
ICONS = {
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "file": '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "steth": '<path d="M5 3H4v6a5 5 0 0 0 10 0V3h-1"/><path d="M9 14v1a5 5 0 0 0 10 0v-2"/><circle cx="19" cy="11" r="2"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 21a2 2 0 0 0 4 0"/>',
    "logout": '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    "shieldok": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "check": '<path d="m5 12 5 5 9-10"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "pulse": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "pill": '<rect x="2" y="8" width="20" height="8" rx="4" transform="rotate(-45 12 12)"/><path d="m8.5 8.5 7 7"/>',
    "drop": '<path d="M12 2.7s-7 7.3-7 12.3a7 7 0 0 0 14 0c0-5-7-12.3-7-12.3z"/>',
    "alert": '<path d="M12 3 2 20h20zM12 10v4M12 17v.01"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "cal": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "hosp": '<path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M12 8v5M9.5 10.5h5"/><path d="M10 21v-4h4v4"/>',
    "eyeoff": '<path d="M9.9 4.2A10 10 0 0 1 12 4c6.5 0 10 8 10 8a17 17 0 0 1-2.3 3.3"/><path d="M6.6 6.6A17 17 0 0 0 2 12s3.5 8 10 8a10 10 0 0 0 5.4-1.6"/><path d="m2 2 20 20"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "users": '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/>',
    "send": '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3"/>',
    "chev": '<path d="m9 5 7 7-7 7"/>',
    "qr": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3"/>',
    "camera": '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/>',
    "arrow": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "back": '<path d="M15 5l-7 7 7 7"/>',
    "trend": '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
    "pencil": '<path d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4"/>',
    "heart": '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/>',
}

LOGO = ICONS["plus"]   # the design's logo mark: a plain plus, drawn like the other icons


@register.simple_tag
def icon(name, size=""):
    """Return the SVG for one icon. size can be "sm" or "lg" for the small and large versions; the actual sizes are
    set in the stylesheet."""
    # An unknown name draws an empty icon instead of crashing the page; tests/test_templates.py catches typos.
    return mark_safe(f'<svg class="i {size}" viewBox="0 0 24 24" aria-hidden="true">{ICONS.get(name, "")}</svg>')


@register.simple_tag
def logo(size=""):
    """The plus used in the MedScan logo tile. size can be "sm" for the small tile in the phone's top bar."""
    return mark_safe(f'<svg class="i {size}" viewBox="0 0 24 24" aria-hidden="true">{LOGO}</svg>')


@register.filter
def initials(name):
    """Turn 'Juan Dela Cruz' into 'JC' for the round avatars."""
    words = str(name).split()
    return (words[0][0] + words[-1][0]) if len(words) > 1 else str(name)[:2]


@register.filter
def tint(user_id):
    """Pick one of four avatar colours from the ID, so the same person always gets the same colour."""
    return ["", "c1", "c2", "c3"][int(user_id) % 4]
