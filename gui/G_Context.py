"""Adds the logged-in user and their notifications to every page (used by the sidebar and panel)."""
from gui import G_Views


def shell(request):
    """Template variables available on every page: user, inbox_items, unread."""
    user = G_Views.current_user(request)
    if not user:
        return {"user": None}
    system = G_Views.system
    return {
        "user": user,
        "inbox_items": system.inbox(user.user_id)[:20],
        "unread": system.unread_count(user.user_id),
    }
