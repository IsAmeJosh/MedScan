"""Adds the logged-in user and their notifications to every page (used by the sidebar, top bar and panel)."""
from gui import G_Views


def shell(request):
    """Template variables available on every page: user, inbox_items, unread, and the sidebar counts."""
    user = G_Views.current_user(request)
    if not user:
        return {"user": None}
    system = G_Views.system
    ctx = {
        "user": user,
        "inbox_items": system.inbox(user.user_id)[:20],
        "unread": system.unread_count(user.user_id),
    }
    if user.role == "Patient":
        ctx["waiting_count"] = system.pending_count_for_patient(user.user_id)
    else:
        ctx["pending_count"] = system.request_summary_for_doctor(user.user_id)["pending"]
    return ctx
