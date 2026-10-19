"""MedScanSystem holds the rules of MedScan: who may see what, and what happens when a doctor asks,
a patient answers, or someone registers. It keeps no data of its own. Every question and every change
goes to MySQL through the repositories in data/, so the database is always the source of truth."""
import re
from datetime import date, datetime, timedelta

from data.D_Access_Repository import AccessRepository
from data.D_Audit_Repository import AuditRepository
from data.D_Doctor_Repository import DoctorRepository
from data.D_Notification_Repository import NotificationRepository
from data.D_Patient_Repository import PatientRepository
from data.D_QR_Repository import QRRepository
from models.M_Medical_Record import BLOOD_TYPES, MedicalRecord
from models.M_Patient_Link import PatientLink
from models.M_QR_Code import QRCode
from models.M_QR_Token import QRToken
from models.M_Scan_Result import ScanResult


class MedScanSystem:
    """The rules of MedScan in one place: who may see whose record, and what happens when a doctor asks, a patient
    answers, someone scans a QR code or an emergency override is used. The views (gui/) call these methods and
    nothing else, and the repositories (data/) do the SQL. That split is abstraction: a view asks 'may this doctor
    open this record?' and never needs to know which tables were checked to answer."""

    BLOOD_TYPES = BLOOD_TYPES
    VIEW_QUIET_MINUTES = 10      # Opening the same record again within this many minutes is not logged a second time.
    EMERGENCY_HOURS = 1          # An emergency override lets the doctor in for this many hours.
    PASSWORD_LENGTH = (6, 25)    # The shortest and longest password allowed.
    MAX_AGE_YEARS = 120
    # The longest text allowed per field. The sizes match the MySQL columns, so a save can never overflow.
    LIMITS = {"Name": 100, "Sex": 20, "Specialty": 100, "Clinic": 150,
              "Each allergy, surgery or medication": 200, "Consultation notes": 5000, "Emergency reason": 500}
    DATE_FORMAT = "%m/%d/%Y"     # How a date of birth is typed in the forms: 04/04/2004 (month/day/year).
    # The ways a mobile number may be written: 09171234567, +639171234567 or 639171234567.
    MOBILE_NUMBER = re.compile(r"(?:\+?63|0)(9\d{9})")

    def __init__(self, db):
        """Build one repository for each kind of data. The system itself keeps no data of its own."""
        self.db = db
        self._patients = PatientRepository(db)
        self._doctors = DoctorRepository(db)
        self._access = AccessRepository(db)
        self._audit = AuditRepository(db)
        self._notes = NotificationRepository(db)
        self._qr = QRRepository(db)

    # ---- registration ----
    def register_patient(self, name, password, sex, date_of_birth, allergies="", surgeries="",
                         contact_number="", medications="", blood_type=""):
        """Create a patient account. Every field is checked first, and if anything is wrong a ValueError is raised
        with a message written for the person to read (the form shows it as it is). Nothing is saved unless every
        check passes. Returns the new Patient."""
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

    def register_doctor(self, name, password, specialty, clinic="", contact_number=""):
        """Create a doctor account. The mobile number is optional. Like register_patient, bad input raises a
        ValueError with a readable message and nothing is saved. Returns the new Doctor."""
        name, password = self._check_credentials(name, password)
        specialty = self._limit((specialty or "").strip(), "Specialty")
        clinic = self._limit((clinic or "").strip(), "Clinic")
        contact_number = self._check_contact(contact_number)
        new_id = self._doctors.add(name, password, specialty, clinic, date.today().year, contact_number)
        return self._doctors.get(new_id)

    def update_contact_number(self, user_id, number):
        """Let a patient or a doctor change their own mobile number (the Profile page). A patient must have one, and
        it must be theirs alone because it is also a way to log in. A doctor's is optional. Returns the user, or
        None if there is no such account."""
        user = self.get_user(user_id, with_record=False)
        if user is None:
            return None
        is_patient = user.role == "Patient"
        number = self._check_contact(number, required=is_patient)
        if is_patient:
            self._ensure_mobile_free(number, except_id=user_id)
        (self._patients if is_patient else self._doctors).set_contact(user_id, number)
        return self.get_user(user_id, with_record=False)

    def update_patient_info(self, patient_id, allergies, surgeries, medications, blood_type, contact_number):
        """Let a patient edit their own history (allergies, surgeries, medications, blood type) and their mobile
        number. Everything is checked before anything is changed, so a mistake in one field cannot leave the record
        half updated. Returns the patient, or None."""
        contact_number = self._check_contact(contact_number, required=True)
        self._ensure_mobile_free(contact_number, except_id=patient_id)
        blood_type = self._check_blood_type(blood_type)
        # Check everything first, so nothing is changed when one field is wrong.
        self._check_items(allergies, surgeries, medications)
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
        """Trim the name and make sure the name and the password are acceptable. Returns the cleaned name and the
        password."""
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
        """Raise a readable error if the text is longer than its field allows. The limits match the MySQL columns, so
        a save can never overflow."""
        limit = cls.LIMITS[field]
        if len(text) > limit:
            raise ValueError(f"{field} is too long (at most {limit} characters).")
        return text

    @classmethod
    def _check_items(cls, *comma_lists):
        """Make sure every allergy, surgery or medication in the comma-separated lists is short enough to save."""
        for text in comma_lists:
            for item in (text or "").split(","):
                cls._limit(item.strip(), "Each allergy, surgery or medication")

    @classmethod
    def _check_birth_date(cls, value):
        """Check a date of birth, given as a date or as text such as 04/04/2004 or 2004-04-04. A date in the future,
        or more than 120 years ago, is refused with a readable error."""
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
        """Return a mobile number in the one form MedScan stores, 09171234567, from any of the ways people write it
        (09171234567, +63 917 123 4567, 63 917 123 4567; spaces, dashes and brackets are ignored). Returns None if
        the text is not a mobile number."""
        text = re.sub(r"[ \-()]", "", (number or "").strip())
        match = cls.MOBILE_NUMBER.fullmatch(text)
        return "0" + match.group(1) if match else None

    @classmethod
    def _check_contact(cls, number, required=False):
        """Check a mobile number and return it as 09171234567. It is optional unless required=True."""
        if not (number or "").strip():
            if required:
                raise ValueError("Enter your mobile number.")
            return ""
        mobile = cls.normalize_mobile(number)
        if mobile is None:
            raise ValueError("Enter a valid mobile number, like 09171234567 or +63 917 123 4567.")
        return mobile

    def _ensure_mobile_free(self, mobile, except_id=None):
        """Make sure no other account already uses this mobile number: one number belongs to one account."""
        owner = self._patients.id_for_mobile(mobile)
        if owner is not None and owner != except_id:
            raise ValueError("That mobile number is already used by another account.")

    @staticmethod
    def _check_blood_type(blood_type):
        """Blood type must be one of the known types, or blank for not set."""
        blood_type = (blood_type or "").strip()
        if blood_type not in BLOOD_TYPES:
            raise ValueError("Please choose a valid blood type.")
        return blood_type

    @staticmethod
    def parse_id(text):
        """Turn '1001' or 'PT-2026-01001' into the number 1001. Returns None when there is no number in the text."""
        parts = re.findall(r"\d+", text or "")
        return int(parts[-1]) if parts else None

    # ---- finding people ----
    def get_user(self, user_id, with_record=True):
        """Find a patient or a doctor by ID, or None. It asks the patients first and then the doctors, so the caller
        does not need to know which kind of account it is. with_record=False skips loading a patient's medical
        record, for places that only need to know who it is and what role they have."""
        return self._patients.get(user_id, with_record) or self._doctors.get(user_id)

    def resolve_login(self, text):
        """Turn what was typed in the login box into a user ID. It accepts an ID number (1001), a full ID
        (PT-2026-01001) or a patient's mobile number written in any accepted way. Returns None when nothing
        matches."""
        mobile = self.normalize_mobile(text)
        if mobile:
            return self._patients.id_for_mobile(mobile)
        return self.parse_id(text)

    def get_patient(self, patient_id, with_record=True):
        """Find a patient by ID, with their full record unless with_record=False. Returns None if there is no such
        patient."""
        return self._patients.get(patient_id, with_record)

    def get_doctor(self, doctor_id):
        """Find a doctor by ID, or None if there is no such doctor."""
        return self._doctors.get(doctor_id)

    def patient_exists(self, patient_id):
        """True if there is a patient with this ID. It is cheaper than get_patient() when the record is not needed."""
        return self._patients.exists(patient_id)

    def authenticate(self, user_id, password):
        """Return the user when the ID and the password both match, otherwise None. The password check itself happens
        inside User.login(), so the password never leaves that class."""
        user = self.get_user(user_id) if user_id is not None else None
        return user if user and user.login(user_id, password) else None

    # ---- the one-time QR code ----
    def current_qr(self, patient_id):
        """The code the patient can show right now: their newest QRToken that has not been used, replaced or run out
        of time. If there is none, a new one is made, so a patient who opens the QR sheet always gets a working
        code."""
        with self.db.unit_of_work():
            return self._qr.newest_usable(patient_id) or self._issue_qr(patient_id)

    def new_qr(self, patient_id):
        """The patient asks for a new code. Every older code stops working at once. Returns the new QRToken."""
        with self.db.unit_of_work():
            self._qr.retire_all(patient_id)
            return self._issue_qr(patient_id)

    def _issue_qr(self, patient_id):
        """Make and save a new secret for the patient and return it as a QRToken."""
        self._qr.add(patient_id, QRToken.make_value())
        return self._qr.newest_usable(patient_id)

    def scan_qr(self, doctor, scanned_text):
        """A doctor scanned a code. Returns a ScanResult that says what happened. A live code (the patient's ID plus
        the one-time secret) is the patient's approval in person: the secret is used up, the doctor is approved (or
        already was), the scan is logged and the patient is told. A plain ID code only finds the patient and
        approves nothing, so knowing someone's ID can never approve a doctor."""
        patient_id, secret = QRCode.parse(scanned_text)
        if patient_id is None:
            return ScanResult(ScanResult.INVALID)
        if secret is None:
            return ScanResult(ScanResult.FOUND, patient_id)
        with self.db.unit_of_work():
            if not self._qr.spend(secret, patient_id):
                return ScanResult(ScanResult.EXPIRED, patient_id)
            already = self._approve_by_scan(doctor.user_id, patient_id)
            self._audit.add_scan(doctor.user_id, patient_id)
            self._notify(patient_id, f"Dr. {doctor.name} scanned your QR code.", kind="scan")
            return ScanResult(ScanResult.ALREADY if already else ScanResult.APPROVED, patient_id)

    def _approve_by_scan(self, doctor_id, patient_id):
        """Make sure this doctor is approved for this patient. A request that is still waiting is approved; otherwise
        a new, already approved one is made. Returns True if the doctor already had access before the scan."""
        history = self._access.history(doctor_id, patient_id)
        if any(request.is_approved() for request in history):
            return True
        waiting = [request for request in history if request.status == "Pending"]
        if waiting:
            self._access.set_status(waiting[0].request_id, "Approved", via="qr")
            # The patient has dealt with that request, so its notifications count as read.
            self._notes.mark_request_read(patient_id, waiting[0].request_id)
        else:
            self._access.add_approved_by_qr(doctor_id, patient_id)
        return False

    # ---- access control ----
    def access_status(self, doctor_id, patient_id):
        """How the doctor stands with the patient, as a word: 'approved', 'pending', 'denied' or 'revoked' (how the
        latest request ended), or 'none' if there never was one."""
        history = [r.status for r in self._access.history(doctor_id, patient_id)]
        if "Approved" in history:
            return "approved"
        if "Pending" in history:
            return "pending"
        if history and history[-1] in ("Denied", "Revoked"):
            return history[-1].lower()
        return "none"

    def request_access(self, doctor, patient_id):
        """A doctor asks a patient for access. Returns the new request, or None if the patient does not exist or the
        doctor already has access or a waiting request (there are never duplicates)."""
        with self.db.unit_of_work():
            # The row lock makes two clicks at once safe: only one of them can answer.
            if not self._patients.exists(patient_id, lock=True):
                return None
            if self.access_status(doctor.user_id, patient_id) in ("approved", "pending"):
                return None
            request = self._access.get(self._access.add(doctor.user_id, patient_id))
            self._notify(patient_id, f"Dr. {doctor.name} requests access to your record.", request.request_id, "request")
            return request

    def respond_to_request(self, request_id, patient_id, approve):
        """The patient answers a request, approving or denying it. Only the patient the request is for can answer, and
        only while it is still Pending. The row is locked while this is checked, so two clicks at once cannot both
        succeed. Returns True if the answer was recorded."""
        with self.db.unit_of_work():
            request = self._access.get(request_id, lock=True)
            if not request or request.patient_id != patient_id or request.status != "Pending":
                return False
            request.approve() if approve else request.deny()
            self._access.set_status(request_id, request.status, request.via)
            # The patient has dealt with that request, so its notifications count as read.
            self._notes.mark_request_read(patient_id, request_id)
            word = "approved" if approve else "denied"
            self._notify(request.doctor_id, f"{self._name_of(patient_id)} {word} your access request.", request_id, word)
            return True

    def doctor_of_request(self, request_id):
        """The doctor who sent one access request, or None. The page uses the name in its message after the patient
        answers ("Allowed. Dr. Santos can now see your record.")."""
        request = self._access.get(request_id)
        return self._doctors.get(request.doctor_id) if request else None

    def revoke_access(self, request_id, patient_id):
        """A patient takes back access they had approved. Returns True if it was revoked."""
        with self.db.unit_of_work():
            request = self._access.get(request_id, lock=True)
            if not request or request.patient_id != patient_id or not request.is_approved():
                return False
            request.revoke()
            self._access.set_status(request_id, request.status, request.via)
            self._notify(request.doctor_id, f"{self._name_of(patient_id)} revoked your access to their record.",
                         request_id, "revoked")
            return True

    def has_access(self, doctor_id, patient_id):
        """True if the patient has approved this doctor and has not taken the approval back."""
        return self._access.has_approved(doctor_id, patient_id)

    def has_emergency_access(self, doctor_id, patient_id):
        """True if this doctor used an emergency override on this patient within the last hour."""
        return self._audit.emergency_active(doctor_id, patient_id, self.EMERGENCY_HOURS)

    def can_view_record(self, doctor_id, patient_id):
        """The one rule that decides who may open a record: a doctor may view it with the patient's approval, or
        during an emergency override."""
        return self.has_access(doctor_id, patient_id) or self.has_emergency_access(doctor_id, patient_id)

    def emergency_access(self, doctor, patient_id, reason):
        """Open a record without the patient's approval. The reason is logged and the patient is told right away.
        Returns the patient, or None if there is no such patient."""
        self._limit(reason, "Emergency reason")
        with self.db.unit_of_work():
            patient = self._patients.get(patient_id, with_record=False)
            if not patient:
                return None
            self._audit.add_emergency(doctor.user_id, patient_id, reason)
            self._notify(patient_id, f"Dr. {doctor.name} opened your record in an emergency: {reason}", kind="emergency")
            return patient

    def open_record(self, doctor, patient_id):
        """Return the patient if this doctor may view the record, and log the view so the patient can see it in
        History. Otherwise None."""
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
        """Add a consultation note, but only if the doctor may view the record. Returns the note, or None."""
        notes = (notes or "").strip()
        if not notes or not self.can_view_record(doctor.user_id, patient_id):
            return None
        self._limit(notes, "Consultation notes")
        patient = self._patients.get(patient_id, with_record=False)
        if not patient:
            return None
        # The doctor builds the note and files it in the patient's record.
        consultation = doctor.add_consultation(patient, notes, None)
        consultation.consultation_id = self._patients.add_consultation(patient_id, consultation)
        self._notify(patient_id, f"Dr. {doctor.name} added a consultation note.", kind="note")
        return consultation

    # ---- read helpers for the pages ----
    def request_rows_for_patient(self, patient_id):
        """A list of (request, doctor) pairs for the requests addressed to this patient, newest first."""
        requests = self._access.for_patient(patient_id)
        doctors = self._doctors.get_many([r.doctor_id for r in requests])
        return [(r, doctors.get(r.doctor_id)) for r in requests]

    def request_rows_for_doctor(self, doctor_id, status=None):
        """A list of (request, patient) pairs for the requests this doctor sent, newest first. status ('Pending',
        'Approved', 'Denied' or 'Revoked') keeps only the requests in that state."""
        requests = self._access.for_doctor(doctor_id, status)
        patients = self._patients.get_many([r.patient_id for r in requests], with_record=False)
        return [(r, patients.get(r.patient_id)) for r in requests]

    def emergency_rows_for_patient(self, patient_id):
        """A list of (log, doctor) pairs for every emergency opening of this patient's record, newest first."""
        logs = self._audit.emergencies_for_patient(patient_id)
        doctors = self._doctors.get_many([e.doctor_id for e in logs])
        return [(e, doctors.get(e.doctor_id)) for e in logs]

    def view_rows_for_patient(self, patient_id):
        """A list of (view, doctor) pairs for every time a doctor opened this patient's record, newest first."""
        views = self._audit.views_for_patient(patient_id)
        doctors = self._doctors.get_many([v.doctor_id for v in views])
        return [(v, doctors.get(v.doctor_id)) for v in views]

    def doctor_groups_for_patient(self, patient_id):
        """The patient's doctors, sorted by where their latest request stands: {"with_access": [...], "waiting":
        [...], "past": [...]}, each a list of (request, doctor, last_view). There is one row per doctor, and the
        newest request wins."""
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
        """The IDs of the requests still waiting for this patient. The bell uses them to show Approve and Deny buttons
        only on those."""
        return set(self._access.pending_request_ids_for_patient(patient_id))

    def request_behind(self, notification):
        """The access request a notification is about, or None if it is not about one."""
        if not notification.related_request_id:
            return None
        return self._access.get(notification.related_request_id)

    def scan_rows_for_patient(self, patient_id):
        """A list of (scan, doctor) pairs for every time a doctor scanned this patient's QR code, newest first."""
        scans = self._audit.scans_for_patient(patient_id)
        doctors = self._doctors.get_many([s.doctor_id for s in scans])
        return [(s, doctors.get(s.doctor_id)) for s in scans]

    def activity_for_patient(self, patient_id):
        """Everything that happened to the patient's record, newest first, for the History tab. Each item is a dict
        with kind ('view', 'emergency_view', 'override', 'scan' or 'declined'), when, ended (for an override: when the
        doctor's emergency access stopped, one EMERGENCY_HOURS after it began; otherwise None), doctor, and detail (the
        reason, for an override). A 'declined' item is a request the patient said no to."""
        items = [{"kind": "emergency_view" if v.via == "emergency" else "view", "when": v.timestamp, "ended": None,
                  "doctor": doctor, "detail": ""} for v, doctor in self.view_rows_for_patient(patient_id)]
        items += [{"kind": "override", "when": e.timestamp, "ended": e.timestamp + timedelta(hours=self.EMERGENCY_HOURS),
                   "doctor": doctor, "detail": e.reason} for e, doctor in self.emergency_rows_for_patient(patient_id)]
        items += [{"kind": "scan", "when": s.timestamp, "ended": None, "doctor": doctor, "detail": ""}
                  for s, doctor in self.scan_rows_for_patient(patient_id)]
        items += [{"kind": "declined", "when": r.decided_at or r.created_at, "ended": None, "doctor": doctor, "detail": ""}
                  for r, doctor in self.request_rows_for_patient(patient_id) if r.status == "Denied"]
        return sorted(items, key=lambda item: item["when"], reverse=True)

    # Which history kinds each chip on the Access page keeps ('all' keeps everything).
    ACTIVITY_CHIPS = {"scan": ("scan",), "approved": ("view",), "emergency": ("override", "emergency_view")}

    @classmethod
    def filter_activity(cls, items, show):
        """Keep one kind of history item for the filter chips on the Access page: 'scan' (a doctor scanned the QR
        code), 'approved' (opened with the patient's OK) or 'emergency' (an override, or a view during one). Any
        other value, such as 'all', keeps everything."""
        kinds = cls.ACTIVITY_CHIPS.get(show)
        return [item for item in items if item["kind"] in kinds] if kinds else list(items)

    @classmethod
    def activity_counts(cls, items):
        """How many items each chip would show, as {'all': n, 'scan': n, 'approved': n, 'emergency': n}."""
        return {show: len(cls.filter_activity(items, show)) for show in ("all", *cls.ACTIVITY_CHIPS)}

    def pending_count_for_patient(self, patient_id):
        """How many requests are waiting for this patient's answer. This is the number on the Access item."""
        return self._access.pending_count_for_patient(patient_id)

    # ---- the doctor's Patients list ----
    # Which link kinds each chip on the Patients page keeps ('all' keeps everything).
    LINK_CHIPS = ("access", "waiting", "emergency", "denied")

    @classmethod
    def _link(cls, patient, request, emergency):
        """Work out the PatientLink for one patient from the doctor's newest request with them (or None) and the
        doctor's newest emergency override on them (or None). An approval beats a waiting request, which beats an
        emergency, which beats a denial; with nothing at all the record is simply locked."""
        if request is not None and request.status == "Approved":
            return PatientLink(patient, "access", request.decided_at or request.created_at, request.via)
        if request is not None and request.status == "Pending":
            return PatientLink(patient, "waiting", request.created_at)
        if emergency is not None:
            return PatientLink(patient, "emergency", emergency.timestamp, ends=emergency.timestamp + timedelta(hours=cls.EMERGENCY_HOURS))
        if request is not None:
            return PatientLink(patient, "denied", request.decided_at or request.created_at)
        return PatientLink(patient, "locked")

    def patient_links_for_doctor(self, doctor_id):
        """One PatientLink for every patient this doctor has asked, scanned or opened in an emergency, in list order
        (access, waiting, emergency, denied; newest first inside each). Requests and logs are read newest first, so
        the first one seen for a patient is the newest, and a dict keeps just that one. That finds the newest in
        one pass, with no extra sorting."""
        newest_request, newest_emergency = {}, {}
        for request in self._access.for_doctor(doctor_id):
            newest_request.setdefault(request.patient_id, request)
        for log in self._audit.emergencies_for_doctor(doctor_id):
            newest_emergency.setdefault(log.patient_id, log)
        ids = list(dict.fromkeys(list(newest_request) + list(newest_emergency)))
        patients = self._patients.get_many(ids, with_record=False)
        links = [self._link(patients[pid], newest_request.get(pid), newest_emergency.get(pid))
                 for pid in ids if pid in patients]
        return sorted(links, key=PatientLink.sort_key)

    def patient_link(self, doctor_id, patient):
        """How this one patient stands with this doctor (a PatientLink). It is used for the patient's page and for
        search results."""
        history = self._access.history(doctor_id, patient.user_id)
        emergencies = [log for log in self._audit.emergencies_for_patient(patient.user_id) if log.doctor_id == doctor_id]
        return self._link(patient, history[-1] if history else None, emergencies[0] if emergencies else None)

    @classmethod
    def filter_links(cls, links, show):
        """Keep one kind of line for the filter chips on the Patients page. Any other value, such as 'all', keeps
        everything."""
        return [link for link in links if link.kind == show] if show in cls.LINK_CHIPS else list(links)

    @classmethod
    def link_counts(cls, links):
        """How many lines each chip would show, as {'all': n, 'access': n, 'waiting': n, 'emergency': n, 'denied': n}."""
        return {show: len(cls.filter_links(links, show)) for show in ("all", *cls.LINK_CHIPS)}

    def find_patients(self, doctor_id, text, limit=10):
        """The Search page. First the patient whose ID or mobile number was typed (anyone, so a doctor can ask a
        patient who is not theirs yet), then this doctor's own patients whose name or ID matches. Each is a
        PatientLink, so the page can show 'Locked', 'Access' and so on. A name never finds someone the doctor has
        no link with, so names cannot be used to browse everyone."""
        needle = (text or "").strip()
        if not needle:
            return []
        found = {}
        exact_id = self.resolve_login(needle)
        exact = self._patients.get(exact_id, with_record=False) if exact_id is not None else None
        if exact is not None:
            found[exact.user_id] = self.patient_link(doctor_id, exact)
        lowered = needle.lower()
        for link in self.patient_links_for_doctor(doctor_id):
            if lowered in link.patient.name.lower():
                found.setdefault(link.patient.user_id, link)
        return list(found.values())[:limit]

    def recent_patient_rows_for_doctor(self, doctor_id, limit=5):
        """A list of (patient, when the doctor last opened them), newest first. Only patients the doctor can still
        open are included, so access that was taken back disappears from the list."""
        recent = self._audit.recent_views_for_doctor(doctor_id, limit * 3)
        patients = self._patients.get_many([pid for pid, _ in recent], with_record=False)
        rows = [(patients[pid], when) for pid, when in recent if pid in patients and self.can_view_record(doctor_id, pid)]
        return rows[:limit]

    def recent_notes_for_doctor(self, doctor_id, limit=2):
        """A list of (patient, Consultation) for the notes this doctor wrote most recently, newest first. Home shows
        them under Recent notes."""
        rows = self._patients.recent_notes_by_doctor(doctor_id, limit)
        patients = self._patients.get_many([pid for pid, _ in rows], with_record=False)
        return [(patients[pid], note) for pid, note in rows if pid in patients]

    def recent_scans_for_doctor(self, doctor_id, limit=3):
        """A list of (patient, when) for the patients this doctor scanned most recently, newest first. The scan page
        shows them under Recent scans."""
        rows = self._audit.scans_for_doctor(doctor_id, limit)
        patients = self._patients.get_many([pid for pid, _ in rows], with_record=False)
        return [(patients[pid], when) for pid, when in rows if pid in patients]

    def month_counts_for_doctor(self, doctor_id):
        """What a doctor did this month, for their Profile: {'patients', 'notes', 'scans', 'emergencies'}."""
        counts = self._audit.counts_this_month(doctor_id)
        counts["notes"] = self._patients.notes_written_this_month(doctor_id)
        return counts

    def note_authors(self, record):
        """The doctors who wrote notes in a record, as a list of (doctor, how many notes), the one with the newest note
        first. My Record shows them under Written by."""
        counts, order = {}, []
        for note in reversed(record.consultations):          # newest first
            if note.doctor_id not in counts:
                order.append(note.doctor_id)
            counts[note.doctor_id] = counts.get(note.doctor_id, 0) + 1
        doctors = self._doctors.get_many(order)
        return [(doctors[did], counts[did]) for did in order if did in doctors]

    def unopened_patients_for_doctor(self, doctor_id):
        """Patients who approved this doctor but whose record the doctor has not opened yet, in ID order. Home lists
        them first."""
        patients = self._patients.get_many(self._access.unopened_approved_patient_ids(doctor_id), with_record=False)
        return [patients[pid] for pid in sorted(patients)]

    def search_my_patients(self, doctor_id, text, limit=6):
        """The doctor's own patients (the ones who approved them) whose name contains the text, or whose ID starts
        with the digits typed. The search box uses this for its suggestions, so it can never suggest a patient the
        doctor has no access to."""
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
        """A list of the patients who have approved this doctor, in ID order."""
        patients = self._patients.get_many(self._access.approved_patient_ids(doctor_id), with_record=False)
        return [patients[pid] for pid in sorted(patients)]

    # ---- notifications ----
    def _notify(self, recipient_id, message, request_id=None, kind="info"):
        """Send a message to one user's inbox. The kind says what it is about, so the page knows where opening it
        leads."""
        self._notes.add(recipient_id, message, request_id, kind)

    def _name_of(self, patient_id):
        """A patient's name, for use inside a message."""
        patient = self._patients.get(patient_id, with_record=False)
        return patient.name if patient else f"Patient #{patient_id}"

    def inbox(self, user_id, limit=None):
        """A user's notifications, newest first, at most `limit` of them."""
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
