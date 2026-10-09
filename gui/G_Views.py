"""Django views. Thin: each one reads the request and calls MedScanSystem."""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from data.D_Setup import choose_store
from logic.L_MedScan_System import MedScanSystem

system = MedScanSystem.load(choose_store())


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


# ---------- before login ----------
def login_view(request):
    """Show the login form and log the user in. The ID can be 1001 or PT-2026-01001."""
    if current_user(request):
        return redirect("dashboard")
    if request.method == "POST":
        uid = system.parse_id(request.POST.get("user_id", ""))
        user = system.authenticate(uid, request.POST.get("password", ""))
        if user:
            request.session["uid"] = user.user_id
            return redirect("dashboard")
        messages.error(request, "Wrong ID number or password.")
    return render(request, "G_Login.html")


def register_view(request):
    """Create a patient or doctor account; show the error if the input is bad."""
    if current_user(request):
        return redirect("dashboard")
    if request.method == "POST":
        f = request.POST
        try:
            if f.get("role") == "Doctor":
                user = system.register_doctor(f.get("name"), f.get("password"), f.get("specialty") or "General")
            else:
                user = system.register_patient(f.get("name"), f.get("password"), f.get("sex", ""),
                                               f.get("age"), f.get("allergies", ""), f.get("surgeries", ""),
                                               contact_number=f.get("contact_number", ""))
        except ValueError as error:
            messages.error(request, str(error))
            return render(request, "G_Register.html", {"form": f})
        system.save()
        request.session["new_id"] = user.display_id
        return redirect("welcome")
    return render(request, "G_Register.html")


def welcome_view(request):
    """Show the new account's ID once, right after registering."""
    new_id = request.session.pop("new_id", None)
    if not new_id:
        return redirect("login")
    return render(request, "G_Welcome.html", {"new_id": new_id})


def logout_view(request):
    """Ask to confirm, then clear the session."""
    if request.method == "POST":
        request.session.flush()
        return redirect("login")
    if not current_user(request):
        return redirect("login")
    return render(request, "G_Logout_Confirm.html")


def notifications_read(request):
    """Called by the notification panel when it opens: marks the inbox as read."""
    user = current_user(request)
    if user and request.method == "POST":
        system.mark_inbox_read(user.user_id)
        system.save()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=403)


# ---------- both roles ----------
def dashboard(request):
    """Patient home (health card, requests, emergency log) or doctor home (request summary)."""
    user = current_user(request)
    if not user:
        return redirect("login")
    if user.role == "Patient":
        return render(request, "G_Patient_Dashboard.html", {
            "record": user.record,
            "requests": system.request_rows_for_patient(user.user_id),
            "emergencies": system.emergency_rows_for_patient(user.user_id),
            "views": system.view_rows_for_patient(user.user_id)[:10],
        })
    return render(request, "G_Doctor_Dashboard.html", {
        "summary": system.request_summary_for_doctor(user.user_id),
        "recent": system.request_rows_for_doctor(user.user_id)[:5],
    })


# ---------- patient pages ----------
def my_record(request):
    """The patient's own record, with a form to edit it."""
    patient = _patient(request)
    if not patient:
        return redirect("dashboard")
    return render(request, "G_My_Record.html", {
        "record": patient.record, "blood_types": system.BLOOD_TYPES,
    })


def update_info(request):
    """Patient edits their allergies, surgeries, medications, blood type and contact number."""
    patient = _patient(request)
    if patient and request.method == "POST":
        f = request.POST
        try:
            system.update_patient_info(patient.user_id, f.get("allergies", ""), f.get("surgeries", ""),
                                       f.get("medications", ""), f.get("blood_type", ""),
                                       f.get("contact_number", ""))
            system.save()
            messages.success(request, "Your information was updated.")
        except ValueError as error:
            messages.error(request, str(error))
    return redirect("my_record")


def profile(request):
    """Account details and the doctors who have access."""
    patient = _patient(request)
    if not patient:
        return redirect("dashboard")
    return render(request, "G_Profile.html", {"requests": system.request_rows_for_patient(patient.user_id)})


def respond(request, rid, decision):
    """Patient approves or denies a request."""
    patient = _patient(request)
    if patient and request.method == "POST":
        approve = decision == "approve"
        if system.respond_to_request(rid, patient.user_id, approve):
            system.save()
            messages.success(request, "Access approved." if approve else "Access denied.")
    return redirect("dashboard")


def revoke(request, rid):
    """Patient takes back access from a doctor they approved earlier."""
    patient = _patient(request)
    if patient and request.method == "POST":
        if system.revoke_access(rid, patient.user_id):
            system.save()
            messages.success(request, "Access revoked.")
    return redirect("profile" if request.POST.get("next") == "profile" else "dashboard")


# ---------- doctor pages ----------
def search_patient(request):
    """Doctor looks up a patient by ID and sees whether the record is locked."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    ctx = {}
    q = request.GET.get("q", "").strip()
    if q:
        patient = system.get_patient(system.parse_id(q))
        ctx["searched"] = q
        ctx["found"] = patient
        if patient:
            ctx["status"] = system.access_status(doctor.user_id, patient.user_id)
    return render(request, "G_Search.html", ctx)


def doctor_requests(request):
    """All access requests the doctor has sent, with their status."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    return render(request, "G_Doctor_Requests.html", {
        "rows": system.request_rows_for_doctor(doctor.user_id),
        "summary": system.request_summary_for_doctor(doctor.user_id),
    })


def send_request(request, pid):
    """Doctor asks a patient for access."""
    doctor = _doctor(request)
    if doctor and request.method == "POST":
        if system.request_access(doctor, pid):
            system.save()
            messages.success(request, "Access request sent. Waiting for the patient to approve.")
        else:
            messages.error(request, "You already have access or a pending request for this patient.")
    return redirect(f"/search/?q={pid}")


def patient_record(request, pid):
    """Show a full record only if the doctor has approval or used emergency access."""
    doctor = _doctor(request)
    if not doctor or not system.get_patient(pid):
        return redirect("dashboard")
    emergency_used = request.session.get(f"emergency_{pid}")
    patient = system.open_record(doctor, pid, emergency_used)
    if not patient:
        messages.error(request, "You need the patient's approval (or an emergency override) to view this record.")
        return redirect(f"/search/?q={pid}")
    return render(request, "G_Record.html", {
        "patient": patient, "record": patient.record,
        "latest": patient.record.latest_consultation(), "emergency": emergency_used,
    })


def emergency(request, pid=None):
    """Confirm and log an emergency override, then open the record."""
    doctor = _doctor(request)
    if not doctor:
        return redirect("dashboard")
    if request.method == "POST":
        target = pid if pid is not None else system.parse_id(request.POST.get("patient_id", ""))
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "An emergency reason is required.")
        elif system.emergency_access(doctor, target, reason):
            request.session[f"emergency_{target}"] = True
            system.save()
            return redirect("record", pid=target)
        else:
            messages.error(request, "No patient with that ID.")
        return render(request, "G_Emergency_Confirm.html",
                      {"patient": system.get_patient(pid), "form": request.POST})
    return render(request, "G_Emergency_Confirm.html", {"patient": system.get_patient(pid)})


def add_consultation(request, pid):
    """Doctor saves a consultation note to the record."""
    doctor = _doctor(request)
    if doctor and request.method == "POST":
        emergency_used = request.session.get(f"emergency_{pid}")
        if system.add_consultation(doctor, pid, request.POST.get("notes", ""), emergency_used):
            system.save()
            messages.success(request, "Consultation saved to the medical record.")
        else:
            messages.error(request, "Could not save the note. You need access to this record, and the note cannot be empty.")
    return redirect("record", pid=pid)
