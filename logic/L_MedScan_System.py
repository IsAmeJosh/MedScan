"""MedScanSystem ties all classes together. The Django website and the console
demo (Main_Driver.py) both use this same class."""
import re
from datetime import datetime, timedelta

from models.M_Patient import Patient
from models.M_Doctor import Doctor
from models.M_Access_Request import AccessRequest
from models.M_Emergency_Log import EmergencyLog
from models.M_Notification import Notification
from models.M_Record_View import RecordView
from models.M_Medical_Record import BLOOD_TYPES


class MedScanSystem:
    """Holds all patients, doctors, requests, logs and notifications, and enforces the access rules."""

    BLOOD_TYPES = BLOOD_TYPES
    VIEW_WINDOW = timedelta(minutes=10)  # reopening a record within this time is not logged again

    def __init__(self):
        self.patients = {}      # id -> Patient
        self.doctors = {}       # id -> Doctor
        self.requests = []
        self.emergency_logs = []
        self.record_views = []
        self.notifications = []
        self._next_patient = 1001
        self._next_doctor = 2001

    # ---- persistence ----
    @staticmethod
    def load(store):
        """Load the system from a store. If the store is empty, start it with the demo accounts."""
        system = store.load()
        if system is None:
            system = MedScanSystem()
            system.attach_store(store)
            system.register_doctor("Reyes", "doc123", "General Medicine")
            system.register_patient("Juan Dela Cruz", "pat123", "Male", 30, "Penicillin", "Appendectomy",
                                    contact_number="09171234567", blood_type="O+")
            system.save()
        system.attach_store(store)
        return system

    def attach_store(self, store):
        """Choose where save() writes (a MySQL database, a pickle file, ...)."""
        self._store = store

    def save(self):
        """Write everything to the attached store. Does nothing without one (the console demo)."""
        store = getattr(self, "_store", None)
        if store:
            store.save(self)

    def restore_counters(self):
        """After loading, make new IDs continue after the highest saved ones."""
        self._next_patient = max(self.patients, default=1000) + 1
        self._next_doctor = max(self.doctors, default=2000) + 1

    def __getstate__(self):
        """Leave the store out when pickling, so a pickle file holds data only."""
        state = self.__dict__.copy()
        state.pop("_store", None)
        return state

    # ---- registration / login ----
    def register_patient(self, name, password, sex, age, allergies="", surgeries="",
                         contact_number="", medications="", blood_type=""):
        """Create a patient. Raises ValueError with a readable message on bad input."""
        name, password = self._check_credentials(name, password)
        try:
            age = int(age or 0)
        except (TypeError, ValueError):
            raise ValueError("Age must be a whole number.")
        if not 0 <= age <= 120:
            raise ValueError("Age must be between 0 and 120.")
        contact_number = self._check_contact(contact_number)
        blood_type = self._check_blood_type(blood_type)
        p = Patient(self._next_patient, name, password, sex, age, contact_number)
        p.update_history(allergies, surgeries, medications, blood_type)
        self.patients[p.user_id] = p
        self._next_patient += 1
        return p

    def register_doctor(self, name, password, specialty):
        """Create a doctor. Raises ValueError with a readable message on bad input."""
        name, password = self._check_credentials(name, password)
        d = Doctor(self._next_doctor, name, password, specialty)
        self.doctors[d.user_id] = d
        self._next_doctor += 1
        return d

    def update_patient_info(self, patient_id, allergies, surgeries, medications, blood_type, contact_number):
        """Let a patient edit their own history and contact number. Returns the patient or None."""
        patient = self.patients.get(patient_id)
        if not patient:
            return None
        contact_number = self._check_contact(contact_number)
        blood_type = self._check_blood_type(blood_type)
        patient.contact_number = contact_number
        patient.update_history(allergies, surgeries, medications, blood_type)
        return patient

    @staticmethod
    def _check_credentials(name, password):
        """Trim the name and make sure a name and password were given."""
        name = (name or "").strip()
        if not name or not password:
            raise ValueError("Name and password are required.")
        return name, password

    @staticmethod
    def _check_contact(number):
        """Contact number is optional; if given it must be 10 to 11 digits (spaces and dashes are ignored)."""
        number = (number or "").strip().replace(" ", "").replace("-", "")
        if number and not (number.isdecimal() and 10 <= len(number) <= 11):
            raise ValueError("Contact number must be 10 to 11 digits.")
        return number

    @staticmethod
    def _check_blood_type(blood_type):
        """Blood type must be one of the known types, or blank."""
        blood_type = (blood_type or "").strip()
        if blood_type not in BLOOD_TYPES:
            raise ValueError("Please choose a valid blood type.")
        return blood_type

    @staticmethod
    def parse_id(text):
        """Turn '1001' or 'PT-2026-01001' into 1001. Returns None if there is no number."""
        parts = re.findall(r"\d+", text or "")
        return int(parts[-1]) if parts else None

    def authenticate(self, user_id, password):
        """Return the user if the ID and password match, otherwise None."""
        user = self.patients.get(user_id) or self.doctors.get(user_id)
        return user if user and user.login(user_id, password) else None

    def get_user(self, user_id):
        """Find a patient or doctor by ID, or None."""
        return self.patients.get(user_id) or self.doctors.get(user_id)

    def get_patient(self, patient_id):
        """Find a patient by ID, or None."""
        return self.patients.get(patient_id)

    # ---- access control ----
    def access_status(self, doctor_id, patient_id):
        """'approved', 'pending', 'denied', 'revoked' (how the latest request ended) or 'none'."""
        mine = [r for r in self.requests if r.doctor_id == doctor_id and r.patient_id == patient_id]
        if any(r.is_approved() for r in mine):
            return "approved"
        if any(r.status == "Pending" for r in mine):
            return "pending"
        if mine and mine[-1].status in ("Denied", "Revoked"):
            return mine[-1].status.lower()
        return "none"

    def request_access(self, doctor, patient_id):
        """Returns the new request, or None if the patient does not exist or the
        doctor already has access or a pending request (no duplicates)."""
        if patient_id not in self.patients:
            return None
        if self.access_status(doctor.user_id, patient_id) in ("approved", "pending"):
            return None
        req = AccessRequest(len(self.requests) + 1, doctor.user_id, patient_id)
        self.requests.append(req)
        self._notify(patient_id, f"Dr. {doctor.name} requests access to your record.", req.request_id)
        return req

    def respond_to_request(self, request_id, patient_id, approve):
        """Only the patient the request is for can answer, and only while it is Pending.
        Returns True if the answer was recorded."""
        req = next((r for r in self.requests if r.request_id == request_id), None)
        if not req or req.patient_id != patient_id or req.status != "Pending":
            return False
        req.approve() if approve else req.deny()
        word = "approved" if approve else "denied"
        self._notify(req.doctor_id, f"{self.patients[patient_id].name} {word} your access request.", req.request_id)
        return True

    def revoke_access(self, request_id, patient_id):
        """A patient takes back access they approved. Returns True if it was revoked."""
        req = next((r for r in self.requests if r.request_id == request_id), None)
        if not req or req.patient_id != patient_id or not req.is_approved():
            return False
        req.revoke()
        self._notify(req.doctor_id, f"{self.patients[patient_id].name} revoked your access to their record.", req.request_id)
        return True

    def has_access(self, doctor_id, patient_id):
        """True if the patient approved this doctor."""
        return any(r.doctor_id == doctor_id and r.patient_id == patient_id and r.is_approved()
                for r in self.requests)

    def can_view_record(self, doctor_id, patient_id, emergency=False):
        """A doctor may view a record with the patient's approval, or in an emergency."""
        return emergency or self.has_access(doctor_id, patient_id)

    def emergency_access(self, doctor, patient_id, reason):
        """Open a record without approval. The reason is logged and the patient is notified."""
        patient = self.patients.get(patient_id)
        if not patient:
            return None
        self.emergency_logs.append(EmergencyLog(len(self.emergency_logs) + 1, doctor.user_id, patient_id, reason))
        self._notify(patient_id, f"Dr. {doctor.name} opened your record in an emergency: {reason}")
        return patient

    def open_record(self, doctor, patient_id, emergency=False):
        """Return the patient if this doctor may view the record, and log the view. Otherwise None."""
        patient = self.patients.get(patient_id)
        if not patient or not self.can_view_record(doctor.user_id, patient_id, emergency):
            return None
        via = "approved" if self.has_access(doctor.user_id, patient_id) else "emergency"
        self._log_view(doctor.user_id, patient_id, via)
        return patient

    def _log_view(self, doctor_id, patient_id, via):
        """Add a view to the log, unless the same doctor just opened the same record."""
        last = next((v for v in reversed(self.record_views)
                     if v.doctor_id == doctor_id and v.patient_id == patient_id), None)
        if last and last.via == via and datetime.now() - last.timestamp < self.VIEW_WINDOW:
            return
        self.record_views.append(RecordView(len(self.record_views) + 1, doctor_id, patient_id, via))

    # ---- consultations ----
    def add_consultation(self, doctor, patient_id, notes, emergency=False):
        """Adds a note only if the doctor may view the record. Returns the note or None."""
        patient = self.patients.get(patient_id)
        if not patient or not notes.strip():
            return None
        if not self.can_view_record(doctor.user_id, patient_id, emergency):
            return None
        return doctor.add_consultation(patient, notes.strip(), self._next_consultation_id())

    def _next_consultation_id(self):
        """Next consultation ID, counted from the saved records so it survives restarts."""
        return 1 + sum(len(p.record.consultations) for p in self.patients.values())

    # ---- read helpers for the pages ----
    def request_rows_for_patient(self, patient_id):
        """[(request, doctor)] addressed to this patient, newest first."""
        return [(r, self.doctors.get(r.doctor_id)) for r in reversed(self.requests) if r.patient_id == patient_id]

    def request_rows_for_doctor(self, doctor_id):
        """[(request, patient)] sent by this doctor, newest first."""
        return [(r, self.patients.get(r.patient_id)) for r in reversed(self.requests) if r.doctor_id == doctor_id]

    def request_summary_for_doctor(self, doctor_id):
        """How many of this doctor's requests are pending, approved or denied."""
        mine = [r for r in self.requests if r.doctor_id == doctor_id]
        return {"pending": sum(r.status == "Pending" for r in mine),
                "approved": sum(r.is_approved() for r in mine),
                "denied": sum(r.status == "Denied" for r in mine),
                "revoked": sum(r.status == "Revoked" for r in mine)}

    def emergency_rows_for_patient(self, patient_id):
        """[(log, doctor)] for every emergency opening of this patient's record, newest first."""
        return [(e, self.doctors.get(e.doctor_id)) for e in reversed(self.emergency_logs) if e.patient_id == patient_id]

    def view_rows_for_patient(self, patient_id):
        """[(view, doctor)] for every time a doctor opened this patient's record, newest first."""
        return [(v, self.doctors.get(v.doctor_id)) for v in reversed(self.record_views) if v.patient_id == patient_id]

    # ---- notifications ----
    def _notify(self, recipient_id, message, request_id=None):
        """Send a message to one user's inbox."""
        Notification(len(self.notifications) + 1, recipient_id, message, request_id).send_notification(self.notifications)

    def inbox(self, user_id):
        """A user's notifications, newest first."""
        return [n for n in reversed(self.notifications) if n.recipient_id == user_id]

    def unread_count(self, user_id):
        """How many of the user's notifications are still unread."""
        return sum(not n.is_read for n in self.inbox(user_id))

    def mark_inbox_read(self, user_id):
        """Mark all of the user's notifications as read."""
        for n in self.inbox(user_id):
            n.mark_as_read()
