"""The Django views. They are kept thin on purpose: each one reads the request, calls a MedScanSystem method and picks
the page to show. The rules themselves live in logic/, so a view never decides who may see what."""
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from urllib.parse import urlencode

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from data.D_Database import Database
from logic.L_MedScan_System import MedScanSystem
from models.M_Scan_Result import ScanResult

db = Database.from_environment()
db.prepare()  # Create the tables and the demo accounts from database/*.sql if they are missing.
system = MedScanSystem(db)

PATIENT_CHIPS = ("all", "access", "waiting", "emergency", "denied")
# old ?tab= addresses (bookmarks) mapped to the filter chips
OLD_PATIENT_TABS = {"mine": "access", "waiting": "waiting", "ended": "denied"}
ACCESS_TABS = ("requests", "doctors", "history")
ACTIVITY_FILTERS = ("all", "scan", "approved", "emergency")
# The page a patient lands on for each destination word a Notification gives (see Notification.destination).
PATIENT_DESTINATIONS = {"requests": "/access/?tab=requests", "history": "/access/?tab=history", "record": "/record/"}


def current_user(request):
    """The logged-in Patient or Doctor, or None. Both kinds come back as a User, so the rest of the code can treat
    them the same way (polymorphism) and only looks at the role when it matters."""
    uid = request.session.get("uid")
    return system.get_user(uid) if uid else None


def _doctor(request):
    """The logged-in user if they are a doctor, otherwise None. The doctor-only views use it as their guard."""
    user = current_user(request)
    return user if user and user.role == "Doctor" else None


def _patient(request):
    """The logged-in user if they are a patient, otherwise None. The patient-only views use it as their guard."""
    user = current_user(request)
    return user if user and user.role == "Patient" else None


def _back_to(request, allowed, default):
    """Redirect to the page named in the form's 'next' field, but only if it is one of our own pages (allowed).
    Otherwise go to the default. That stops a made-up form from sending someone to another site."""
    target = request.POST.get("next")
    return redirect(target if target in allowed else default)


def _paginate(request, items, per_page=10):
    """Cut a long list into pages of 10. Returns (page, query), where query repeats the other URL parameters (such as
    a filter) so the Previous and Next links keep them."""
    page = Paginator(items, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


# ---------- before login ----------
def login_view(request):
    """Show the login form and log the person in. The ID box accepts 1001, PT-2026-01001 or a patient's mobile number.
    A wrong ID or password gives one message that does not say which of the two was wrong."""
    if current_user(request):
        return redirect("dashboard")
    if request.method == "POST":
        uid = system.resolve_login(request.POST.get("user_id", ""))   # Accepts an ID, a full ID, or a mobile number.
        user = system.authenticate(uid, request.POST.get("password", ""))
        if user:
            request.session["uid"] = user.user_id
            return redirect("dashboard")
        messages.error(request, "Wrong ID number or password.")
    elif request.GET.get("expired"):
        messages.info(request, f"You were logged out after {settings.IDLE_LOGOUT_MINUTES} minutes without activity.")
    return render(request, "G_Login.html")


def register_view(request):
    """Create a patient or doctor account. It is one form with a Patient / Doctor switch (?role=patient or
    ?role=doctor, patient when there is none). If the input is bad, the error is shown on the form and what was
    typed is kept. After a successful sign-up the person is logged in and sees the save-your-ID screen."""
    if current_user(request):
        return redirect("dashboard")
    if request.method == "POST":
        f = request.POST
        try:
            if f.get("role") == "Doctor":
                user = system.register_doctor(f.get("name"), f.get("password"), f.get("specialty") or "General",
                                              f.get("clinic", ""), f.get("contact_number", ""))
            else:
                user = system.register_patient(f.get("name"), f.get("password"), f.get("sex", ""),
                                               f.get("date_of_birth"), f.get("allergies", ""), f.get("surgeries", ""),
                                               contact_number=f.get("contact_number", ""))
        except ValueError as error:
            messages.error(request, str(error))
            return render(request, "G_Register.html", {"form": f, "role": "Doctor" if f.get("role") == "Doctor" else "Patient"})
        request.session["uid"] = user.user_id      # Registering also logs the new person in.
        return redirect("id_ready")                # First stop: the "save your ID" screen.
    role = {"patient": "Patient", "doctor": "Doctor"}.get(request.GET.get("role", ""), "Patient")
    return render(request, "G_Register.html", {"role": role})


def logout_view(request):
    """Show the log-out question. Once it is confirmed, clear the session and go back to the login page."""
    if request.method == "POST":
        request.session.flush()
        return redirect("login")
    if not current_user(request):
        return redirect("login")
    return render(request, "G_Logout_Confirm.html")


# ---------- notifications ----------
def notifications_poll(request):
    """Answered every few seconds by the page: how many notifications are unread, the sidebar counts, and the list for
    the bell panel. The page uses it to update the bell without reloading. It is marked passive, so it does not
    keep an idle session alive."""
    request.medscan_passive = True   # This is not the person doing anything, so it must not keep an idle session alive.
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
        "html": render_to_string("G_Notification_List.html", {"inbox_items": inbox, "user": user}),
    }
    if patient:
        data["waiting"] = system.pending_count_for_patient(user.user_id)
    else:
        data["ready"] = len(system.unopened_patients_for_doctor(user.user_id))
    return JsonResponse(data)


def notifications_read(request):
    """Called by the notification panel's "Mark all as read" button."""
    user = current_user(request)
    if user and request.method == "POST":
        system.mark_inbox_read(user.user_id)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=403)


def notification_open(request, nid):
    """Mark one notification as read and go to what it is about. A doctor whose request was approved goes straight to
    that patient's record, and otherwise to the Patients list filtered to Waiting or Denied. A patient goes to the
    page that matches the message: Requests, My Record or History (see Notification.destination)."""
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
        return redirect("/patients/?show=denied" if behind and behind.status != "Pending" else "/patients/?show=waiting")
    return redirect(PATIENT_DESTINATIONS[note.destination("Patient")])


def keepalive(request):
    """The page calls this while the person is active. Opening it renews the session, which starts the idle logout
    timer again."""
    if request.session.get("uid") and request.method == "POST":
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=403)


# ---------- both roles ----------
def dashboard(request):
    """Home. A patient sees their ID card, the requests waiting for an answer and their latest activity. A doctor sees
    the patients who approved them but have not been opened yet, the patients they opened recently, and the
    requests still waiting."""
    user = current_user(request)
    if not user:
        return redirect("login")
    if user.role == "Patient":
        groups = system.doctor_groups_for_patient(user.user_id)
        return render(request, "G_Patient_Dashboard.html", {
            "record": user.record,
            "waiting": groups["waiting"],
            "team": groups["with_access"][:3],
            "activity": system.activity_for_patient(user.user_id)[:3],
        })
    return render(request, "G_Doctor_Dashboard.html", {
        "ready": system.unopened_patients_for_doctor(user.user_id),
        "recent": system.recent_patient_rows_for_doctor(user.user_id),
        "waiting": system.request_rows_for_doctor(user.user_id, "Pending"),
        "notes": system.recent_notes_for_doctor(user.user_id),
    })


def id_ready(request):
    """The screen right after registering: the new MedScan ID to save, a link to download it, and a button on to Home.
    The password is never shown here."""
    user = current_user(request)
    if not user:
        return redirect("login")
    return render(request, "G_Id_Ready.html", {"plain": True})


def id_print(request):
    """The printable ID page. The browser's Print dialog saves it as a PDF, so no PDF library is needed. It shows the
    ID, name, account type, the day it was made and a masked mobile number. Never the password. Opening it with
    ?auto=1 starts the Print dialog by itself."""
    user = current_user(request)
    if not user:
        return redirect("login")
    return render(request, "G_Id_Print.html", {"plain": True, "auto": request.GET.get("auto") == "1"})


def settings_page(request):
    """Settings, for both roles. Log out lives here and nowhere else, so there is one place to find it. Nothing on it is
    stored yet except what the Account rows lead to, so the view only shows the page."""
    if not current_user(request):
        return redirect("login")
    return render(request, "G_Settings.html")


def profile(request):
    """Profile: the account details of whoever is logged in."""
    user = current_user(request)
    if not user:
        return redirect("login")
    month = system.month_counts_for_doctor(user.user_id) if user.role == "Doctor" else None
    return render(request, "G_Profile.html", {"month": month})


def profile_contact(request):
    """Save the mobile number from the Profile page's "Edit contact info" sheet (patients and doctors)."""
    user = current_user(request)
    if not user:
        return redirect("login")
    if request.method == "POST":
        try:
            system.update_contact_number(user.user_id, request.POST.get("contact_number", ""))
            messages.success(request, "Your contact number was updated.")
        except ValueError as error:
            messages.error(request, str(error))
    return redirect("profile")


def qr_page(request):
    """Scan QR code, for doctors. A patient's code is a sheet that opens on whatever page they are on, so patients
    have no page of their own here."""
    user = current_user(request)
    if not user:
        return redirect("login")
    if user.role == "Patient":
        return redirect("/dashboard/?sheet=qr")        # A patient's code is a sheet on every page (see G_Base.html).
    return render(request, "G_QR.html", {"scans": system.recent_scans_for_doctor(user.user_id)})


def _qr_reply(patient, token):
    """The patient's live code as JSON for the QR sheet: the picture, the seconds it still works, and its ID. The
    sheet compares the ID to know when the code was replaced."""
    return JsonResponse({"ok": True, "svg": patient.qr_code(token).svg(), "seconds": token.seconds_left,
                         "id": token.token_id})


def qr_code(request):
    """The patient's live QR code (made if they have none). The sheet asks for it when it opens and every few seconds
    while it stays open, so it follows a code that was used or replaced. Looking does not count as being active."""
    request.medscan_passive = True
    patient = _patient(request)
    if not patient:
        return JsonResponse({"ok": False}, status=403)
    return _qr_reply(patient, system.current_qr(patient.user_id))


def qr_new(request):
    """The patient pressed "Make a new code": the old one stops working and a new one is returned."""
    patient = _patient(request)
    if not patient or request.method != "POST":
        return JsonResponse({"ok": False}, status=403)
    return _qr_reply(patient, system.new_qr(patient.user_id))


def qr_scan(request):
    """The scanner found a code. A live one-time code is the patient's approval in person: the doctor is let in and
    lands on the record. A plain ID code only finds the patient (the same result as typing the ID), so knowing an ID
    can never approve anyone."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    result = system.scan_qr(doctor, request.GET.get("code", ""))
    if result.opens_record:
        messages.success(request, "Scan successful. Access approved and logged." if result.outcome == ScanResult.APPROVED
                         else "Scan logged. You already had access.")
        return redirect("record", pid=result.patient_id)
    if result.outcome == ScanResult.FOUND:
        return redirect("record", pid=result.patient_id)        # The locked page: it says what the doctor can do next.
    if result.outcome == ScanResult.EXPIRED:
        messages.error(request, "That code was already used or has run out of time. Ask the patient to show it again.")
    else:
        messages.error(request, "That is not a MedScan patient code. Ask the patient to open Show my QR code.")
    return redirect("qr")


# ---------- patient pages ----------
def my_record(request):
    """My Record: the patient's own details and medical record, with a form to edit them."""
    patient = _patient(request)
    if not patient:
        return redirect("dashboard")
    return render(request, "G_My_Record.html", {
        "record": patient.record, "blood_types": system.BLOOD_TYPES, "authors": system.note_authors(patient.record),
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


def access(request):
    """Access: one page with three tabs. Requests (waiting for the patient's answer), Doctors (who can open the record
    now) and History (everything that happened to the record, with filter chips: All, QR scan, Approved and
    Emergency). It opens on Requests when something is waiting, and on Doctors otherwise."""
    patient = _patient(request)
    if not patient:
        return redirect("dashboard")
    groups = system.doctor_groups_for_patient(patient.user_id)
    tab = request.GET.get("tab")
    if tab not in ACCESS_TABS:
        tab = "requests" if groups["waiting"] else "doctors"
    ctx = {"tab": tab, "waiting": groups["waiting"], "with_access": groups["with_access"]}
    if tab == "history":
        show = request.GET.get("show") if request.GET.get("show") in ACTIVITY_FILTERS else "all"
        items = system.activity_for_patient(patient.user_id)
        ctx["show"] = show
        ctx["counts"] = system.activity_counts(items)
        ctx["activity"], ctx["query"] = _paginate(request, system.filter_activity(items, show))
    return render(request, "G_Access.html", ctx)


def respond(request, rid, decision):
    """The patient approves or denies a request. The buttons on Home, on Access and in the Review sheet all post here."""
    patient = _patient(request)
    approve = decision == "approve"
    if patient and request.method == "POST":
        doctor = system.doctor_of_request(rid)
        if system.respond_to_request(rid, patient.user_id, approve):
            if approve:
                # the "undo" tag makes the page show the Undo link (a demo placeholder, it does nothing yet)
                messages.success(request, f"Allowed. Dr. {doctor.name} can now see your record.", extra_tags="undo")
            else:
                messages.success(request, "Request declined.")
    return _back_to(request, ["access"], "dashboard")


def revoke(request, rid):
    """Patient takes back access from a doctor they approved earlier."""
    patient = _patient(request)
    if patient and request.method == "POST":
        if system.revoke_access(rid, patient.user_id):
            messages.success(request, "Access revoked.")
    return _back_to(request, ["access"], "dashboard")


# ---------- doctor pages ----------
def patients(request):
    """Patients: one list of everyone this doctor has asked, scanned or opened in an emergency, with chips:
    All, With access, Waiting, Emergency, Denied. Each line opens that patient's page."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    # /patients/?q= still works (bookmarks); searching lives on /search/
    if request.GET.get("q"):
        return redirect("/search/?" + urlencode({"q": request.GET["q"]}))
    show = request.GET.get("show") or OLD_PATIENT_TABS.get(request.GET.get("tab"), "all")
    show = show if show in PATIENT_CHIPS else "all"
    links = system.patient_links_for_doctor(doctor.user_id)
    ctx = {"show": show, "counts": system.link_counts(links)}
    ctx["rows"], ctx["query"] = _paginate(request, system.filter_links(links, show))
    return render(request, "G_Patients.html", ctx)


def search(request):
    """Search: find a patient by ID or mobile number (any patient, to send a request), or one of the doctor's own
    patients by name. Each result says how the patient stands with the doctor and opens their page."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    q = request.GET.get("q", "").strip()
    return render(request, "G_Search.html", {"q": q, "results": system.find_patients(doctor.user_id, q)})


def patient_suggest(request):
    """The search box's suggestions: this doctor's own patients matching what is typed. Never anyone else."""
    request.medscan_passive = True   # Typing in a box is not a reason to renew the session by itself.
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
    return redirect("record", pid=pid)


def patient_record(request, pid):
    """The Patient page, one page with two states. Open (the doctor has approval, or an emergency override from the
    last hour): the record, with Notes / Medical / Info. Locked: only who the patient is, and what the doctor can do
    next (scan their code, send a request, or emergency access). The locked state never receives the record."""
    doctor = _doctor(request)
    if not doctor or not system.patient_exists(pid):
        return redirect("dashboard")
    patient = system.open_record(doctor, pid)
    if patient:
        return render(request, "G_Patient.html", {
            "patient": patient, "record": patient.record, "open": True, "link": system.patient_link(doctor.user_id, patient),
            "emergency": not system.has_access(doctor.user_id, pid)})
    patient = system.get_patient(pid, with_record=False)
    return render(request, "G_Patient.html", {
        "patient": patient, "open": False, "link": system.patient_link(doctor.user_id, patient)})


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
