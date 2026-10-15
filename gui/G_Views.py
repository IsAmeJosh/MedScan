"""Django views. Thin: each one reads the request and calls MedScanSystem."""
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from data.D_Database import Database
from logic.L_MedScan_System import MedScanSystem

db = Database.from_environment()
db.prepare()  # creates the tables and the test accounts from database/*.sql if they are missing
system = MedScanSystem(db)

PATIENT_TABS = ("mine", "waiting", "ended")


def current_user(request):
    """The logged-in Patient or Doctor, treated as a User (polymorphism), or None."""
    uid = request.session.get("uid")
    return system.get_user(uid) if uid else None


def _doctor(request):
    """The logged-in user if they are a doctor, otherwise None."""
    user = current_user(request)
    return user if user and user.role == "Doctor" else None


def _patient(request):
    """The logged-in user if they are a patient, otherwise None."""
    user = current_user(request)
    return user if user and user.role == "Patient" else None


def _back_to(request, allowed, default):
    """Redirect to the page named in the form's 'next' field if it is one of ours, otherwise to default."""
    target = request.POST.get("next")
    return redirect(target if target in allowed else default)


def _paginate(request, items, per_page=10):
    """One page of a long list. Returns (page, query), where query repeats the other URL parameters
    (such as a filter) so the Previous and Next links keep them."""
    page = Paginator(items, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def _from_script(request):
    """True when the page's own script made the request (the buttons in the notification panel),
    so the answer should be JSON instead of a redirect."""
    return request.headers.get("X-Requested-With") == "fetch"


# ---------- before login ----------
def login_view(request):
    """Show the login form and log the user in. The ID can be 1001, PT-2026-01001 or a patient's mobile number."""
    if current_user(request):
        return redirect("dashboard")
    if request.method == "POST":
        uid = system.resolve_login(request.POST.get("user_id", ""))   # an ID, a full ID, or a mobile number
        user = system.authenticate(uid, request.POST.get("password", ""))
        if user:
            request.session["uid"] = user.user_id
            return redirect("dashboard")
        messages.error(request, "Wrong ID number or password.")
    elif request.GET.get("expired"):
        messages.info(request, f"You were logged out after {settings.IDLE_LOGOUT_MINUTES} minutes without activity.")
    return render(request, "G_Login.html")


def register_view(request):
    """Create a patient or doctor account. First a page asks which one (no role in the address), then a short
    form for that role (?role=patient or ?role=doctor); the error is shown on the form if the input is bad."""
    if current_user(request):
        return redirect("dashboard")
    if request.method == "POST":
        f = request.POST
        try:
            if f.get("role") == "Doctor":
                user = system.register_doctor(f.get("name"), f.get("password"), f.get("specialty") or "General",
                                              f.get("clinic", ""))
            else:
                user = system.register_patient(f.get("name"), f.get("password"), f.get("sex", ""),
                                               f.get("date_of_birth"), f.get("allergies", ""), f.get("surgeries", ""),
                                               contact_number=f.get("contact_number", ""))
        except ValueError as error:
            messages.error(request, str(error))
            return render(request, "G_Register.html", {"form": f, "role": f.get("role")})
        request.session["uid"] = user.user_id      # registering also logs you in
        request.session["welcome"] = True          # the dashboard shows the ID card once
        return redirect("dashboard")
    role = {"patient": "Patient", "doctor": "Doctor"}.get(request.GET.get("role", ""))
    return render(request, "G_Register.html", {"role": role})


def logout_view(request):
    """Ask to confirm, then clear the session."""
    if request.method == "POST":
        request.session.flush()
        return redirect("login")
    if not current_user(request):
        return redirect("login")
    return render(request, "G_Logout_Confirm.html")


# ---------- notifications ----------
def notifications_poll(request):
    """Answered every few seconds by the page: how many notifications are unread, the sidebar counts and the
    list for the panel. The page then updates the bell without reloading."""
    request.medscan_passive = True   # this does not count as activity, or it would keep an idle session alive
    uid = request.session.get("uid")
    user = system.get_user(uid, with_record=False) if uid else None
    if not user:
        return JsonResponse({"ok": False}, status=403)
    inbox = system.inbox(user.user_id, 20)
    patient = user.role == "Patient"
    data = {
        "ok": True,
        "unread": system.unread_count(user.user_id),
        "latest": next((n.message for n in inbox if not n.is_read), ""),
        "html": render_to_string("G_Notification_List.html", {
            "inbox_items": inbox,
            "pending_ids": system.pending_request_ids_for_patient(user.user_id) if patient else set()}),
    }
    if patient:
        data["waiting"] = system.pending_count_for_patient(user.user_id)
    else:
        data["ready"] = len(system.unopened_patients_for_doctor(user.user_id))
    return JsonResponse(data)


def notifications_read(request):
    """Called by the notification panel's "Mark all read" button."""
    user = current_user(request)
    if user and request.method == "POST":
        system.mark_inbox_read(user.user_id)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=403)


def notification_open(request, nid):
    """Mark one notification as read and go to what it is about: a doctor whose request was approved goes
    straight to the record, a patient goes to Privacy."""
    user = current_user(request)
    if not user:
        return redirect("login")
    note = system.open_notification(user.user_id, nid)
    if note is None:
        return redirect("dashboard")
    if user.role == "Doctor":
        behind = system.request_behind(note)
        if behind and behind.is_approved():
            return redirect("record", pid=behind.patient_id)
        return redirect("/patients/?tab=ended" if behind and behind.status != "Pending" else "/patients/?tab=waiting")
    return redirect("privacy" if note.related_request_id else "/privacy/?tab=activity")


def keepalive(request):
    """The page calls this while the user is active. Opening it starts the idle logout timer again."""
    if request.session.get("uid") and request.method == "POST":
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=403)


# ---------- both roles ----------
def dashboard(request):
    """Patient home (what needs an answer, health snapshot, recent activity) or doctor home
    (patients ready to open, recently opened, requests waiting)."""
    user = current_user(request)
    if not user:
        return redirect("login")
    welcome = request.session.pop("welcome", False)
    if user.role == "Patient":
        groups = system.doctor_groups_for_patient(user.user_id)
        return render(request, "G_Patient_Dashboard.html", {
            "welcome": welcome,
            "record": user.record,
            "waiting": groups["waiting"],
            "doctors": (groups["with_access"] + groups["waiting"])[:4],   # who can open the record now, or soon
            "activity": system.activity_for_patient(user.user_id)[:2],
            "profile": system.profile_progress(user),
        })
    week = system.notes_this_week(user.user_id)
    return render(request, "G_Doctor_Dashboard.html", {
        "welcome": welcome,
        "stats": system.doctor_stats(user.user_id),
        "ready": system.unopened_patients_for_doctor(user.user_id),
        "recent": system.recent_patients_for_doctor(user.user_id),
        "week": week, "week_total": sum(day["count"] for day in week),
        "feed": system.inbox(user.user_id, 4),
    })


def qr_page(request):
    """QR Code. A patient sees their own code to show; a doctor sees the scanner. Only patients have a code."""
    user = current_user(request)
    if not user:
        return redirect("login")
    qr_svg = user.qr_code().svg() if user.role == "Patient" else ""
    return render(request, "G_QR.html", {"qr_svg": qr_svg})


def qr_scan(request):
    """The scanner found a code. If it is a MedScan patient code, show the same result as typing that ID in the
    search box, so scanning never opens a record by itself: access still needs the patient's approval."""
    if not _doctor(request):
        return redirect("dashboard")
    patient_id = system.patient_id_from_qr(request.GET.get("code", ""))
    if patient_id is None:
        messages.error(request, "That is not a MedScan patient code. Ask the patient to open My QR Code.")
        return redirect("qr")
    return redirect(f"/patients/?q={patient_id}")


# ---------- patient pages ----------
def my_record(request):
    """My Health: the patient's details and medical record, with a form to edit them."""
    patient = _patient(request)
    if not patient:
        return redirect("dashboard")
    return render(request, "G_My_Record.html", {
        "record": patient.record, "blood_types": system.BLOOD_TYPES,
    })


def update_info(request):
    """Patient edits their allergies, surgeries, medications, blood type and mobile number."""
    patient = _patient(request)
    if patient and request.method == "POST":
        f = request.POST
        try:
            system.update_patient_info(patient.user_id, f.get("allergies", ""), f.get("surgeries", ""),
                                       f.get("medications", ""), f.get("blood_type", ""),
                                       f.get("contact_number", ""))
            messages.success(request, "Your information was updated.")
        except ValueError as error:
            messages.error(request, str(error))
    return redirect("my_record")


def privacy(request):
    """Privacy: which doctors can open the record and what they asked for (tab Doctors),
    and everything that happened to the record (tab Activity)."""
    patient = _patient(request)
    if not patient:
        return redirect("dashboard")
    tab = "activity" if request.GET.get("tab") == "activity" else "doctors"
    ctx = {"tab": tab, "doctors": system.doctor_groups_for_patient(patient.user_id)}
    ctx["doctor_total"] = sum(len(group) for group in ctx["doctors"].values())
    activity = system.activity_for_patient(patient.user_id)
    ctx["activity_total"] = len(activity)
    if tab == "activity":
        ctx["activity"], ctx["query"] = _paginate(request, activity)
    return render(request, "G_Privacy.html", ctx)


def respond(request, rid, decision):
    """Patient approves or denies a request. The notification panel's buttons ask for JSON instead of a page."""
    patient = _patient(request)
    approve = decision == "approve"
    if patient and request.method == "POST":
        done = system.respond_to_request(rid, patient.user_id, approve)
        if _from_script(request):
            return JsonResponse({"ok": done, "status": "Approved" if approve else "Denied"}, status=200 if done else 409)
        if done:
            messages.success(request, "Access approved." if approve else "Access denied.")
    elif _from_script(request):
        return JsonResponse({"ok": False}, status=403)
    return _back_to(request, ["privacy"], "dashboard")


def revoke(request, rid):
    """Patient takes back access from a doctor they approved earlier."""
    patient = _patient(request)
    if patient and request.method == "POST":
        if system.revoke_access(rid, patient.user_id):
            messages.success(request, "Access revoked.")
    return _back_to(request, ["privacy"], "dashboard")


# ---------- doctor pages ----------
def patients(request):
    """Patients: look someone up by ID or mobile number (the result shows what you can do next), and the
    doctor's patients in three tabs: mine (they approved), waiting (not answered yet), ended (denied or taken back)."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    tab = request.GET.get("tab") if request.GET.get("tab") in PATIENT_TABS else "mine"
    groups = system.patient_groups_for_doctor(doctor.user_id)
    ctx = {"tab": tab, "counts": {name: len(rows) for name, rows in groups.items()}}
    ctx["rows"], ctx["query"] = _paginate(request, groups[tab])
    q = request.GET.get("q", "").strip()
    if q:
        uid = system.resolve_login(q)
        found = system.get_patient(uid) if uid else None
        ctx.update(searched=q, found=found)
        if found:
            ctx["status"] = system.access_status(doctor.user_id, found.user_id)
        else:   # maybe it was a name: show the doctor's own patients with that name
            ctx["matches"] = system.search_my_patients(doctor.user_id, q, limit=10)
    return render(request, "G_Patients.html", ctx)


def patient_suggest(request):
    """The search box's suggestions: this doctor's own patients matching what is typed. Never anyone else."""
    request.medscan_passive = True   # typing in a box is not a reason to renew a session by itself
    doctor = _doctor(request)
    if not doctor:
        return JsonResponse({"ok": False}, status=403)
    found = system.search_my_patients(doctor.user_id, request.GET.get("q", ""))
    return JsonResponse({"ok": True, "items": [
        {"name": p.name, "id": p.display_id, "url": f"/patient/{p.user_id}/"} for p in found]})


def send_request(request, pid):
    """Doctor asks a patient for access."""
    doctor = _doctor(request)
    if doctor and request.method == "POST":
        if system.request_access(doctor, pid):
            messages.success(request, "Access request sent. Waiting for the patient to approve.")
        else:
            messages.error(request, "You already have access or a pending request for this patient.")
    return redirect(f"/patients/?q={pid}")


def patient_record(request, pid):
    """Show a full record only if the doctor has approval, or an emergency override from the last hour."""
    doctor = _doctor(request)
    if not doctor or not system.patient_exists(pid):
        return redirect("dashboard")
    patient = system.open_record(doctor, pid)
    if not patient:
        messages.error(request, "You need the patient's approval (or an emergency override) to view this record.")
        return redirect(f"/patients/?q={pid}")
    has_access = system.has_access(doctor.user_id, pid)
    return render(request, "G_Record.html", {
        "patient": patient, "record": patient.record,
        "latest": patient.record.latest_consultation(),
        "emergency": not has_access, "has_access": has_access,
    })


def emergency(request, pid=None):
    """Open a record in an emergency: the reason is logged and the patient is told. The pop-up in every page
    posts here; this page is the same thing for browsers without scripts."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    if request.method == "POST":
        target = pid if pid is not None else system.resolve_login(request.POST.get("patient_id", ""))
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "An emergency reason is required.")
        else:
            try:
                opened = system.emergency_access(doctor, target, reason)
            except ValueError as error:
                opened = None
                messages.error(request, str(error))
            else:
                if opened:
                    return redirect("record", pid=target)
                messages.error(request, "No patient with that ID.")
        return render(request, "G_Emergency_Confirm.html", {
            "patient": system.get_patient(pid), "form": request.POST})
    return render(request, "G_Emergency_Confirm.html", {"patient": system.get_patient(pid)})


def add_consultation(request, pid):
    """Doctor saves a consultation note to the record."""
    doctor = _doctor(request)
    if doctor and request.method == "POST":
        try:
            saved = system.add_consultation(doctor, pid, request.POST.get("notes", ""))
        except ValueError as error:
            messages.error(request, str(error))
        else:
            if saved:
                messages.success(request, "Consultation saved to the medical record.")
            else:
                messages.error(request, "Could not save the note. You need access to this record, and the note cannot be empty.")
    return redirect("record", pid=pid)
