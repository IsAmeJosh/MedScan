"""Adds the logged-in user and their notifications to every page. The sidebar, the top bar and the notification panel
all read them."""
from django.conf import settings

from gui import G_Views


def shell(request):
    """Template variables available on every page: user, inbox_items, unread, the sidebar counts and, for a patient,
    the IDs of the requests still waiting (they get Approve and Deny buttons in the panel)."""
    user = G_Views.current_user(request)
    if not user:
        return {"user": None}
    system = G_Views.system
    ctx = {
        "user": user,
        "idle_minutes": settings.IDLE_LOGOUT_MINUTES,
        "poll_seconds": settings.NOTIFICATION_POLL_SECONDS,
        "inbox_items": system.inbox(user.user_id, 20),
        "unread": system.unread_count(user.user_id),
        "pending_ids": set(),
    }
    if user.role == "Patient":
        ctx["pending_ids"] = system.pending_request_ids_for_patient(user.user_id)
        ctx["waiting_count"] = len(ctx["pending_ids"])
    else:
        # Doctors: patients who approved but have not been opened yet.
        ctx["ready_count"] = len(system.unopened_patients_for_doctor(user.user_id))
    return ctx
