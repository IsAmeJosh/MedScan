from django.contrib import messages
from django.shortcuts import redirect, render

from logic.L_MedScan_System import MedScanSystem

system = MedScanSystem.load()


def current_user(request):
    uid = request.session.get("uid")
    return system.get_user(uid) if uid else None


def _doctor(request):
    user = current_user(request)
    return user if user and user.role == "Doctor" else None


def login_view(request):
    if request.method == "POST":
        try:
            uid = int(request.POST["user_id"])
        except ValueError:
            uid = -1
        user = system.authenticate(uid, request.POST["password"])
        if user:
            request.session["uid"] = user.user_id
            return redirect("dashboard")
        messages.error(request, "Wrong ID number or password.")
    return render(request, "G_Login.html")


def register_view(request):
    if request.method == "POST":
        f = request.POST
        if f["role"] == "Doctor":
            user = system.register_doctor(f["name"], f["password"], f.get("specialty") or "General")
        else:
            user = system.register_patient(f["name"], f["password"], f.get("sex", ""),
                                           int(f.get("age") or 0),
                                           f.get("allergies", ""), f.get("surgeries", ""))
        system.save()
        messages.success(request, f"Registered! Your ID number is {user.user_id}. Use it to log in.")
        return redirect("login")
    return render(request, "G_Register.html")


def logout_view(request):
    if request.method == "POST":
        request.session.flush()
        return redirect("login")
    if not current_user(request):
        return redirect("login")
    return render(request, "G_Logout_Confirm.html")


def dashboard(request):
    user = current_user(request)
    if not user:
        return redirect("login")
    inbox = system.inbox(user.user_id)
    ctx = {"user": user, "inbox": [(n, n.is_read) for n in inbox]}
    for n in inbox:
        n.markAsRead()
    if user.role == "Patient":
        ctx["requests"] = [r for r in system.requests if r.patient_id == user.user_id]
        ctx["emergencies"] = [e for e in system.emergency_logs if e.patient_id == user.user_id]
        ctx["record"] = user.record
        system.save()
        return render(request, "G_Patient_Dashboard.html", ctx)
    q = request.GET.get("q", "").strip()
    if q.isdigit():
        patient = system.patients.get(int(q))
        ctx["searched"] = q
        ctx["found"] = patient
        if patient:
            ctx["has_access"] = system.has_access(user.user_id, patient.user_id)
    system.save()
    return render(request, "G_Doctor_Dashboard.html", ctx)


def patient_record(request, pid):
    doctor = _doctor(request)
    patient = system.patients.get(pid)
    if not doctor or not patient:
        return redirect("dashboard")
    emergency_used = request.session.get(f"emergency_{pid}")
    if not system.has_access(doctor.user_id, pid) and not emergency_used:
        messages.error(request, "You need the patient's approval (or an emergency override) to view this record.")
        return redirect(f"/dashboard/?q={pid}")
    return render(request, "G_Record.html", {
        "user": doctor, "patient": patient, "record": patient.record,
        "latest": patient.record.latest_consultation(), "emergency": emergency_used,
    })


def send_request(request, pid):
    doctor = _doctor(request)
    if doctor and request.method == "POST" and system.request_access(doctor, pid):
        system.save()
        messages.success(request, "Access request sent. Waiting for the patient to approve.")
    return redirect(f"/dashboard/?q={pid}")


def respond(request, rid, decision):
    user = current_user(request)
    if user and user.role == "Patient" and request.method == "POST" and 0 < rid <= len(system.requests):
        if system.requests[rid - 1].patient_id == user.user_id:
            system.respond_to_request(rid, decision == "approve")
            system.save()
    return redirect("dashboard")


def emergency(request, pid):
    doctor = _doctor(request)
    patient = system.patients.get(pid)
    if not doctor or not patient:
        return redirect("dashboard")
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if reason and system.emergency_access(doctor, pid, reason):
            request.session[f"emergency_{pid}"] = True
            system.save()
            return redirect("record", pid=pid)
        messages.error(request, "An emergency reason is required.")
        return redirect(f"/dashboard/?q={pid}")
    return render(request, "G_Emergency_Confirm.html", {"patient": patient})


def add_consultation(request, pid):
    doctor = _doctor(request)
    patient = system.patients.get(pid)
    notes = request.POST.get("notes", "").strip()
    if doctor and patient and request.method == "POST" and notes:
        doctor.add_consultation(patient, notes)
        system.save()
        messages.success(request, "Consultation saved to the medical record.")
    return redirect("record", pid=pid)


def update_history(request):
    user = current_user(request)
    if user and user.role == "Patient" and request.method == "POST":
        user.update_history(request.POST.get("allergies", ""), request.POST.get("surgeries", ""))
        system.save()
        messages.success(request, "History updated.")
    return redirect("dashboard")
