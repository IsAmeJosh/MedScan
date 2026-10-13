"""MedScanSystem holds the rules of MedScan: who may see what, and what happens when a doctor asks,
a patient answers, or someone registers. It keeps no data of its own. Every question and every change
goes to MySQL through the repositories in data/, so the database is always the source of truth."""
import re
from datetime import date, datetime

from data.D_Access_Repository import AccessRepository
from data.D_Audit_Repository import AuditRepository
from data.D_Doctor_Repository import DoctorRepository
from data.D_Notification_Repository import NotificationRepository
from data.D_Patient_Repository import PatientRepository
from models.M_Medical_Record import BLOOD_TYPES, MedicalRecord


class MedScanSystem:
    """Enforces the access rules and coordinates the repositories."""

    BLOOD_TYPES = BLOOD_TYPES
    VIEW_QUIET_MINUTES = 10      # opening the same record again within this time is not logged again
    EMERGENCY_HOURS = 1          # an emergency override lets the doctor in for this long
    PASSWORD_LENGTH = (6, 25)    # shortest and longest password
    MAX_AGE_YEARS = 120
    # longest text allowed per field (the same sizes as the MySQL columns, so a save can never overflow)
    LIMITS = {"Name": 100, "Sex": 20, "Specialty": 100, "Clinic": 150,
              "Each allergy, surgery or medication": 200, "Consultation notes": 5000, "Emergency reason": 500}
    DATE_FORMAT = "%m/%d/%Y"     # how a date of birth is typed in the forms: 04/04/2004 (month/day/year)
    MOBILE_NUMBER = re.compile(r"(?:\+?63|0)(9\d{9})")  # 09171234567, +639171234567 or 639171234567

    def __init__(self, db):
        self.db = db
        self._patients = PatientRepository(db)
        self._doctors = DoctorRepository(db)
        self._access = AccessRepository(db)
        self._audit = AuditRepository(db)
        self._notes = NotificationRepository(db)

    # ---- registration ----
    def register_patient(self, name, password, sex, date_of_birth, allergies="", surgeries="",
                         contact_number="", medications="", blood_type=""):
        """Create a patient. Raises ValueError with a readable message on bad input."""
        name, password = self._check_credentials(name, password)
        sex = self._limit(sex or "", "Sex")
        born = self._check_birth_date(date_of_birth)
        contact_number = self._check_contact(contact_number, required=True)
        self._ensure_mobile_free(contact_number)
        blood_type = self._check_blood_type(blood_type)
        self._check_items(allergies, surgeries, medications)
        record = MedicalRecord(None)
        record.replace_history(allergies, surgeries, medications, blood_type)
        new_id = self._patients.add(name, password, sex, born, contact_number, date.today().year, record)
        return self._patients.get(new_id)

    def register_doctor(self, name, password, specialty, clinic=""):
        """Create a doctor. Raises ValueError with a readable message on bad input."""
        name, password = self._check_credentials(name, password)
        specialty = self._limit((specialty or "").strip(), "Specialty")
        clinic = self._limit((clinic or "").strip(), "Clinic")
        new_id = self._doctors.add(name, password, specialty, clinic, date.today().year)
        return self._doctors.get(new_id)

    def update_patient_info(self, patient_id, allergies, surgeries, medications, blood_type, contact_number):
        """Let a patient edit their own history and contact number. Returns the patient or None."""
        contact_number = self._check_contact(contact_number, required=True)
        self._ensure_mobile_free(contact_number, except_id=patient_id)
        blood_type = self._check_blood_type(blood_type)
        self._check_items(allergies, surgeries, medications)  # check everything before changing anything
        patient = self._patients.get(patient_id)
        if not patient:
            return None
        patient.contact_number = contact_number
        patient.update_history(allergies, surgeries, medications, blood_type)
        self._patients.update_info(patient_id, contact_number, patient.record)
        return patient

    # ---- checking input ----
    @classmethod
    def _check_credentials(cls, name, password):
        """Trim the name and make sure the name and password are acceptable."""
        name = (name or "").strip()
        password = password or ""
        if not name or not password:
            raise ValueError("Name and password are required.")
        cls._limit(name, "Name")
        shortest, longest = cls.PASSWORD_LENGTH
        if not shortest <= len(password) <= longest:
            raise ValueError(f"Password must be {shortest} to {longest} characters.")
        return name, password

    @classmethod
    def _limit(cls, text, field):
        """Raise a readable error if the text is longer than the field allows."""
        limit = cls.LIMITS[field]
        if len(text) > limit:
            raise ValueError(f"{field} is too long (at most {limit} characters).")
        return text

    @classmethod
    def _check_items(cls, *comma_lists):
        """Every allergy, surgery or medication in the comma-separated lists must be short enough."""
        for text in comma_lists:
            for item in (text or "").split(","):
                cls._limit(item.strip(), "Each allergy, surgery or medication")

    @classmethod
    def _check_birth_date(cls, value):
        """A date of birth (a date, or text like 04/04/2004 or 2004-04-04) that is not in the future
        or more than 120 years ago."""
        if isinstance(value, datetime):
            value = value.date()
        if not isinstance(value, date):
            text = str(value or "").strip()
            value = None
            for parse in (lambda t: datetime.strptime(t, cls.DATE_FORMAT).date(), date.fromisoformat):
                try:
                    value = parse(text)
                    break
                except ValueError:
                    continue
            if value is None:
                raise ValueError("Enter a valid date of birth like 04/04/2004 (month/day/year).")
        today = date.today()
        if value > today:
            raise ValueError("Date of birth cannot be in the future.")
        if value.year < today.year - cls.MAX_AGE_YEARS:
            raise ValueError(f"Date of birth cannot be more than {cls.MAX_AGE_YEARS} years ago.")
        return value

    @classmethod
    def normalize_mobile(cls, number):
        """09171234567 for any accepted way of writing a mobile number (09171234567, +63 917 123 4567,
        63 917 123 4567; spaces, dashes and brackets are ignored), or None if it is not one."""
        text = re.sub(r"[ \-()]", "", (number or "").strip())
        match = cls.MOBILE_NUMBER.fullmatch(text)
        return "0" + match.group(1) if match else None

    @classmethod
    def _check_contact(cls, number, required=False):
        """A mobile number saved as 09171234567. It is optional unless required=True."""
        if not (number or "").strip():
            if required:
                raise ValueError("Enter your mobile number.")
            return ""
        mobile = cls.normalize_mobile(number)
        if mobile is None:
            raise ValueError("Enter a valid mobile number, like 09171234567 or +63 917 123 4567.")
        return mobile

    def _ensure_mobile_free(self, mobile, except_id=None):
        """One mobile number belongs to one account."""
        owner = self._patients.id_for_mobile(mobile)
        if owner is not None and owner != except_id:
            raise ValueError("That mobile number is already used by another account.")

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

    # ---- finding people ----
    def get_user(self, user_id, with_record=True):
        """Find a patient or doctor by ID, or None. with_record=False skips a patient's medical record
        (for places that only need to know who it is and what role they have)."""
        return self._patients.get(user_id, with_record) or self._doctors.get(user_id)

    def resolve_login(self, text):
        """Turn what was typed in the login box into a user ID: an ID number (1001), a full ID (PT-2026-01001),
        or a patient's mobile number written any accepted way. None if nothing matches."""
        mobile = self.normalize_mobile(text)
        if mobile:
            return self._patients.id_for_mobile(mobile)
        return self.parse_id(text)

    def get_patient(self, patient_id):
        """Find a patient (with their full record) by ID, or None."""
        return self._patients.get(patient_id)

    def get_doctor(self, doctor_id):
        """Find a doctor by ID, or None."""
        return self._doctors.get(doctor_id)

    def patient_exists(self, patient_id):
        """True if there is a patient with this ID."""
        return self._patients.exists(patient_id)

    def authenticate(self, user_id, password):
        """Return the user if the ID and password match, otherwise None."""
        user = self.get_user(user_id) if user_id is not None else None
        return user if user and user.login(user_id, password) else None

    # ---- access control ----
    def access_status(self, doctor_id, patient_id):
        """'approved', 'pending', 'denied', 'revoked' (how the latest request ended) or 'none'."""
        history = [r.status for r in self._access.history(doctor_id, patient_id)]
        if "Approved" in history:
            return "approved"
        if "Pending" in history:
            return "pending"
        if history and history[-1] in ("Denied", "Revoked"):
            return history[-1].lower()
        return "none"

    def request_access(self, doctor, patient_id):
        """Returns the new request, or None if the patient does not exist or the
        doctor already has access or a pending request (no duplicates)."""
        with self.db.unit_of_work():
            if not self._patients.exists(patient_id, lock=True):  # the lock makes two clicks at once safe
                return None
            if self.access_status(doctor.user_id, patient_id) in ("approved", "pending"):
                return None
            request = self._access.get(self._access.add(doctor.user_id, patient_id))
            self._notify(patient_id, f"Dr. {doctor.name} requests access to your record.", request.request_id)
            return request

    def respond_to_request(self, request_id, patient_id, approve):
        """Only the patient the request is for can answer, and only while it is Pending.
        Returns True if the answer was recorded."""
        with self.db.unit_of_work():
            request = self._access.get(request_id, lock=True)
            if not request or request.patient_id != patient_id or request.status != "Pending":
                return False
            request.approve() if approve else request.deny()
            self._access.set_status(request_id, request.status)
            self._notes.mark_request_read(patient_id, request_id)   # the patient has dealt with that message
            word = "approved" if approve else "denied"
            self._notify(request.doctor_id, f"{self._name_of(patient_id)} {word} your access request.", request_id)
            return True

    def revoke_access(self, request_id, patient_id):
        """A patient takes back access they approved. Returns True if it was revoked."""
        with self.db.unit_of_work():
            request = self._access.get(request_id, lock=True)
            if not request or request.patient_id != patient_id or not request.is_approved():
                return False
            request.revoke()
            self._access.set_status(request_id, request.status)
            self._notify(request.doctor_id, f"{self._name_of(patient_id)} revoked your access to their record.",
                         request_id)
            return True

    def has_access(self, doctor_id, patient_id):
        """True if the patient approved this doctor."""
        return self._access.has_approved(doctor_id, patient_id)

    def has_emergency_access(self, doctor_id, patient_id):
        """True if this doctor used an emergency override on this patient within the last hour."""
        return self._audit.emergency_active(doctor_id, patient_id, self.EMERGENCY_HOURS)

    def can_view_record(self, doctor_id, patient_id):
        """A doctor may view a record with the patient's approval, or during an emergency override."""
        return self.has_access(doctor_id, patient_id) or self.has_emergency_access(doctor_id, patient_id)

    def emergency_access(self, doctor, patient_id, reason):
        """Open a record without approval. The reason is logged and the patient is notified.
        Returns the patient, or None if there is no such patient."""
        self._limit(reason, "Emergency reason")
        with self.db.unit_of_work():
            patient = self._patients.get(patient_id, with_record=False)
            if not patient:
                return None
            self._audit.add_emergency(doctor.user_id, patient_id, reason)
            self._notify(patient_id, f"Dr. {doctor.name} opened your record in an emergency: {reason}")
            return patient

    def open_record(self, doctor, patient_id):
        """Return the patient if this doctor may view the record, and log the view. Otherwise None."""
        if self.has_access(doctor.user_id, patient_id):
            via = "approved"
        elif self.has_emergency_access(doctor.user_id, patient_id):
            via = "emergency"
        else:
            return None
        patient = self._patients.get(patient_id)
        if patient:
            self._audit.log_view(doctor.user_id, patient_id, via, self.VIEW_QUIET_MINUTES)
        return patient

    # ---- consultations ----
    def add_consultation(self, doctor, patient_id, notes):
        """Adds a note only if the doctor may view the record. Returns the note or None."""
        notes = (notes or "").strip()
        if not notes or not self.can_view_record(doctor.user_id, patient_id):
            return None
        self._limit(notes, "Consultation notes")
        patient = self._patients.get(patient_id, with_record=False)
        if not patient:
            return None
        consultation = doctor.add_consultation(patient, notes, None)  # builds the note and files it in the record
        consultation.consultation_id = self._patients.add_consultation(patient_id, consultation)
        return consultation

    # ---- read helpers for the pages ----
    def request_rows_for_patient(self, patient_id):
        """[(request, doctor)] addressed to this patient, newest first."""
        requests = self._access.for_patient(patient_id)
        doctors = self._doctors.get_many([r.doctor_id for r in requests])
        return [(r, doctors.get(r.doctor_id)) for r in requests]

    def request_rows_for_doctor(self, doctor_id, status=None):
        """[(request, patient)] sent by this doctor, newest first. status ('Pending', 'Approved', 'Denied'
        or 'Revoked') keeps only requests in that state."""
        requests = self._access.for_doctor(doctor_id, status)
        patients = self._patients.get_many([r.patient_id for r in requests], with_record=False)
        return [(r, patients.get(r.patient_id)) for r in requests]

    def request_summary_for_doctor(self, doctor_id):
        """How many of this doctor's requests are pending, approved, denied or revoked."""
        return self._access.summary_for_doctor(doctor_id)

    def emergency_rows_for_patient(self, patient_id):
        """[(log, doctor)] for every emergency opening of this patient's record, newest first."""
        logs = self._audit.emergencies_for_patient(patient_id)
        doctors = self._doctors.get_many([e.doctor_id for e in logs])
        return [(e, doctors.get(e.doctor_id)) for e in logs]

    def emergency_rows_for_doctor(self, doctor_id):
        """[(log, patient)] for every emergency opening by this doctor, newest first."""
        logs = self._audit.emergencies_for_doctor(doctor_id)
        patients = self._patients.get_many([e.patient_id for e in logs], with_record=False)
        return [(e, patients.get(e.patient_id)) for e in logs]

    def view_rows_for_patient(self, patient_id):
        """[(view, doctor)] for every time a doctor opened this patient's record, newest first."""
        views = self._audit.views_for_patient(patient_id)
        doctors = self._doctors.get_many([v.doctor_id for v in views])
        return [(v, doctors.get(v.doctor_id)) for v in views]

    def doctor_groups_for_patient(self, patient_id):
        """The patient's doctors, sorted by where their latest request stands:
        {"with_access": [...], "waiting": [...], "past": [...]}, each a list of
        (request, doctor, last_view). One row per doctor (the newest request wins)."""
        groups = {"with_access": [], "waiting": [], "past": []}
        last_views = self._audit.last_views_by_doctor(patient_id)
        seen = set()
        for request, doctor in self.request_rows_for_patient(patient_id):
            if request.doctor_id in seen:
                continue
            seen.add(request.doctor_id)
            group = {"Approved": "with_access", "Pending": "waiting"}.get(request.status, "past")
            groups[group].append((request, doctor, last_views.get(request.doctor_id)))
        return groups

    def pending_request_ids_for_patient(self, patient_id):
        """The IDs of the requests still waiting for this patient (their notifications get Approve/Deny buttons)."""
        return set(self._access.pending_request_ids_for_patient(patient_id))

    def request_behind(self, notification):
        """The access request a notification is about, or None."""
        if not notification.related_request_id:
            return None
        return self._access.get(notification.related_request_id)

    def activity_for_patient(self, patient_id):
        """Everything that happened to the patient's record, newest first. Each item is a dict with
        kind ('view', 'emergency_view' or 'override'), when, doctor and detail (the reason for an override)."""
        items = [{"kind": "emergency_view" if v.via == "emergency" else "view", "when": v.timestamp,
                  "doctor": doctor, "detail": ""} for v, doctor in self.view_rows_for_patient(patient_id)]
        items += [{"kind": "override", "when": e.timestamp, "doctor": doctor, "detail": e.reason}
                  for e, doctor in self.emergency_rows_for_patient(patient_id)]
        return sorted(items, key=lambda item: item["when"], reverse=True)

    def pending_count_for_patient(self, patient_id):
        """How many requests are waiting for this patient's answer."""
        return self._access.pending_count_for_patient(patient_id)

    def patient_groups_for_doctor(self, doctor_id):
        """The doctor's patients sorted by where the newest request with each one stands:
        {"mine": [...], "waiting": [...], "ended": [...]}, each a list of (request, patient), newest first.
        'ended' means the patient denied the request or took the access back."""
        requests = self._access.for_doctor(doctor_id)
        patients = self._patients.get_many([r.patient_id for r in requests])
        groups = {"mine": [], "waiting": [], "ended": []}
        seen = set()
        for request in requests:
            if request.patient_id in seen:
                continue
            seen.add(request.patient_id)
            group = {"Approved": "mine", "Pending": "waiting"}.get(request.status, "ended")
            groups[group].append((request, patients.get(request.patient_id)))
        return groups

    def unopened_patients_for_doctor(self, doctor_id):
        """Patients who approved this doctor but whose record the doctor has not opened yet, in ID order."""
        patients = self._patients.get_many(self._access.unopened_approved_patient_ids(doctor_id), with_record=False)
        return [patients[pid] for pid in sorted(patients)]

    def recent_patients_for_doctor(self, doctor_id, limit=5):
        """The patients whose records this doctor opened most recently, newest first, that the doctor can
        still open (access that was taken back is left out)."""
        ids = self._audit.recent_patient_ids_for_doctor(doctor_id, limit * 3)
        patients = self._patients.get_many(ids, with_record=False)
        usable = [patients[pid] for pid in ids if pid in patients and self.can_view_record(doctor_id, pid)]
        return usable[:limit]

    def search_my_patients(self, doctor_id, text, limit=6):
        """The doctor's own patients (those who approved them) whose name contains the text, or whose
        ID starts with the digits typed. Used for the search box's suggestions."""
        needle = (text or "").strip().lower()
        if not needle:
            return []
        digits = re.sub(r"\D", "", needle)
        found = []
        for patient in self.patients_for_doctor(doctor_id):
            by_name = needle in patient.name.lower()
            by_id = bool(digits) and (str(patient.user_id).startswith(digits) or patient.display_id.lower().startswith(needle))
            if by_name or by_id:
                found.append(patient)
        return found[:limit]

    def patients_for_doctor(self, doctor_id):
        """[patient] who have approved this doctor, in ID order."""
        patients = self._patients.get_many(self._access.approved_patient_ids(doctor_id), with_record=False)
        return [patients[pid] for pid in sorted(patients)]

    def doctor_stats(self, doctor_id):
        """Numbers for the doctor's dashboard cards."""
        summary = self.request_summary_for_doctor(doctor_id)
        return {"patients": len(self._access.approved_patient_ids(doctor_id)), "pending": summary["pending"],
                "notes": self._patients.consultation_count_for_doctor(doctor_id),
                "emergencies": self._audit.emergency_count(doctor_id)}

    def notes_this_week(self, doctor_id):
        """The notes this doctor wrote on each of the last 7 days, oldest first, for the bar chart:
        [{"label": "Mon", "count": 2, "height": 30, "today": False}, ...] (height is a percentage of the busiest day)."""
        counts = self._patients.consultation_days_for_doctor(doctor_id, 7)
        today = date.today()
        days = [date.fromordinal(today.toordinal() - back) for back in range(6, -1, -1)]
        busiest = max([counts.get(day, 0) for day in days] + [1])
        return [{"label": day.strftime("%a"), "count": counts.get(day, 0), "today": day == today,
                 "height": max(4, round(100 * counts.get(day, 0) / busiest))} for day in days]

    def profile_progress(self, patient):
        """How complete a patient's health profile is, for the 'Finish your health profile' card:
        {"done": [names], "todo": [names], "percent": 60}. Mobile number and date of birth are always done
        (registering needs them); blood type, allergies and medications are what is left to add."""
        record = patient.record
        steps = [("Mobile number", True), ("Date of birth", True), ("Blood type", bool(record.blood_type)),
                 ("Allergies", bool(record.allergies)), ("Medications", bool(record.medications))]
        done = [name for name, filled in steps if filled]
        return {"done": done, "todo": [name for name, filled in steps if not filled],
                "percent": round(100 * len(done) / len(steps))}

    # ---- notifications ----
    def _notify(self, recipient_id, message, request_id=None):
        """Send a message to one user's inbox."""
        self._notes.add(recipient_id, message, request_id)

    def _name_of(self, patient_id):
        """A patient's name for use in a message."""
        patient = self._patients.get(patient_id, with_record=False)
        return patient.name if patient else f"Patient #{patient_id}"

    def inbox(self, user_id, limit=None):
        """A user's notifications, newest first (at most `limit` of them)."""
        return self._notes.inbox(user_id, limit)

    def open_notification(self, user_id, notification_id):
        """Mark one of the user's notifications as read and return it, or None if it is not theirs."""
        return self._notes.mark_read(user_id, notification_id)

    def unread_count(self, user_id):
        """How many of the user's notifications are still unread."""
        return self._notes.unread_count(user_id)

    def mark_inbox_read(self, user_id):
        """Mark all of the user's notifications as read."""
        self._notes.mark_all_read(user_id)
