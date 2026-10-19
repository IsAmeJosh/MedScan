"""Reads and writes patients, their medical record (surgeries and the health items) and their consultation notes."""
import pymysql

from models.M_Consultation import Consultation
from models.M_Health_Item import HealthItem
from models.M_Patient import Patient

DUPLICATE_KEY = 1062  # MySQL's error number for "that value is already used"
MOBILE_TAKEN = "That mobile number is already used by another account."
COLUMNS = ("patient_id, name, password, sex, date_of_birth, mobile_number, blood_type, created_year, password_changed_at, "
           "height_cm, weight_kg, emergency_name, emergency_relationship, emergency_mobile")
# The details a patient may edit, and the column each one is saved in (the names are fixed here, never user input).
EDITABLE_COLUMNS = {"date_of_birth": "date_of_birth", "sex": "sex", "blood_type": "blood_type", "height_cm": "height_cm",
                    "weight_kg": "weight_kg", "contact_number": "mobile_number", "emergency_name": "emergency_name",
                    "emergency_relationship": "emergency_relationship", "emergency_mobile": "emergency_mobile"}
HEALTH_COLUMNS = ("item_id, patient_id, kind, name, severity, reaction, status, dose, frequency, date_on, added_by_role, added_by_id, "
                  "added_by_name, added_at")
# The details a health item may hold, and the column of each (fixed here, never user input).
HEALTH_VALUES = ("name", "severity", "reaction", "status", "dose", "frequency", "date_on")
ADDERS = {"allergy": "add_allergy", "condition": "add_condition", "medication": "add_medication", "vaccine": "add_vaccine"}


class PatientRepository:
    """The only place that writes SQL about patients and their medical records (allergies, conditions, medications, vaccines,
    surgeries and consultation notes). The rest of the program asks for Patient objects and never sees a query (abstraction).
    Each method is one or a few targeted statements."""

    def __init__(self, db):
        """Keep the Database that every query goes through."""
        self.db = db

    # ---- writing ----
    def add(self, name, password, sex, date_of_birth, contact_number, created_year, record):
        """Insert a new patient together with their starting medical record. Returns the new patient's ID."""
        try:
            with self.db.unit_of_work():
                with self.db.cursor() as cur:
                    cur.execute("INSERT INTO tb_patients (name, password, sex, date_of_birth, mobile_number, "
                                "blood_type, created_year) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (name, password, sex, date_of_birth, contact_number, record.blood_type, created_year))
                    patient_id = cur.lastrowid
                self._write_surgeries(patient_id, record)
                for kind in ("allergy", "condition", "medication", "vaccine"):      # what was typed while registering
                    for item in getattr(record, HealthItem.LISTS[kind]):
                        self.add_health_item(patient_id, kind, {"name": str(item)}, "patient", patient_id, name)
        except pymysql.err.IntegrityError as error:  # Someone else saved this mobile number at the very same moment.
            if error.args[0] == DUPLICATE_KEY:
                raise ValueError(MOBILE_TAKEN) from error
            raise
        return patient_id

    def update_details(self, patient_id, changes, record=None):
        """Save only the details given: changes is {field: value} using the names in EDITABLE_COLUMNS. Given a record, its list of
        past surgeries is rewritten too. All of it is saved together or not at all."""
        try:
            with self.db.unit_of_work():
                if changes:
                    columns = ", ".join(f"{EDITABLE_COLUMNS[field]} = %s" for field in changes)
                    with self.db.cursor() as cur:
                        cur.execute(f"UPDATE tb_patients SET {columns} WHERE patient_id = %s", (*changes.values(), patient_id))
                if record is not None:
                    self._write_surgeries(patient_id, record)
        except pymysql.err.IntegrityError as error:  # the same mobile number saved by someone else a moment ago
            if error.args[0] == DUPLICATE_KEY:
                raise ValueError(MOBILE_TAKEN) from error
            raise

    def set_contact(self, patient_id, contact_number):
        """Save only the patient's mobile number."""
        try:
            with self.db.cursor() as cur:
                cur.execute("UPDATE tb_patients SET mobile_number = %s WHERE patient_id = %s", (contact_number, patient_id))
        except pymysql.err.IntegrityError as error:
            if error.args[0] == DUPLICATE_KEY:
                raise ValueError(MOBILE_TAKEN) from error
            raise

    def _write_surgeries(self, patient_id, record):
        """Rewrite the patient's past surgeries from the record, so the table always matches what the record holds."""
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM tb_medical_items WHERE patient_id = %s AND item_type = 'surgery'", (patient_id,))
            if record.surgeries:
                cur.executemany("INSERT INTO tb_medical_items (patient_id, item_type, item_name) VALUES (%s, 'surgery', %s)",
                                [(patient_id, name) for name in record.surgeries])

    # ---- the health items: allergies, conditions, medications and vaccines ----
    @staticmethod
    def _health_item(row):
        """Make a HealthItem from one database row."""
        return HealthItem(row["name"], row["item_id"], row["kind"], row["severity"], row["reaction"], row["status"], row["dose"],
                          row["frequency"], row["date_on"], row["added_by_role"], row["added_by_id"], row["added_by_name"],
                          row["added_at"])

    def add_health_item(self, patient_id, kind, values, by_role, by_id, by_name):
        """Add one item (kind is allergy, condition, medication or vaccine). values holds only the details that apply, using the
        names in HEALTH_VALUES. who added it is kept with it. Returns the new item's ID."""
        names = [field for field in HEALTH_VALUES if field in values]
        columns = ", ".join(["patient_id", "kind", *names, "added_by_role", "added_by_id", "added_by_name"])
        marks = ", ".join(["%s"] * (len(names) + 5))
        with self.db.cursor() as cur:
            cur.execute(f"INSERT INTO tb_health_items ({columns}) VALUES ({marks})",
                        (patient_id, kind, *[values[field] for field in names], by_role, by_id, by_name))
            return cur.lastrowid

    def get_health_item(self, item_id):
        """One item, or None."""
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {HEALTH_COLUMNS} FROM tb_health_items WHERE item_id = %s", (item_id,))
            row = cur.fetchone()
            return self._health_item(row) if row else None

    def health_owner(self, item_id):
        """The ID of the patient an item belongs to, or None when there is no such item."""
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id FROM tb_health_items WHERE item_id = %s", (item_id,))
            row = cur.fetchone()
            return row["patient_id"] if row else None

    def update_health_item(self, item_id, values):
        """Change the details given (names in HEALTH_VALUES) and leave who added it and when as they were."""
        names = [field for field in HEALTH_VALUES if field in values]
        if not names:
            return
        with self.db.cursor() as cur:
            cur.execute(f"UPDATE tb_health_items SET {', '.join(f'{field} = %s' for field in names)} WHERE item_id = %s",
                        (*[values[field] for field in names], item_id))

    def remove_health_item(self, item_id):
        """Delete one item."""
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM tb_health_items WHERE item_id = %s", (item_id,))

    def replace_health_names(self, patient_id, kind, names, by_role, by_id, by_name):
        """Make the items of one kind exactly these names: items already there with the same name keep their details, the others
        are removed, and new names are added by whoever is given."""
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                cur.execute("SELECT item_id, name FROM tb_health_items WHERE patient_id = %s AND kind = %s ORDER BY item_id",
                            (patient_id, kind))
                existing = cur.fetchall()
            keep = {row["name"].lower() for row in existing if row["name"].lower() in {n.lower() for n in names}}
            for row in existing:
                if row["name"].lower() not in keep:
                    self.remove_health_item(row["item_id"])
            for name in names:
                if name.lower() not in keep:
                    self.add_health_item(patient_id, kind, {"name": name}, by_role, by_id, by_name)
                    keep.add(name.lower())

    def add_consultation(self, patient_id, consultation):
        """Save a consultation note. Returns the new note's ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_consultations (patient_id, doctor_id, doctor_name, notes) "
                        "VALUES (%s, %s, %s, %s)",
                        (patient_id, consultation.doctor_id, consultation.doctor_name, consultation.notes))
            return cur.lastrowid

    def recent_notes_by_doctor(self, doctor_id, limit):
        """A list of (patient ID, Consultation) for the notes this doctor wrote most recently, newest first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT consultation_id, patient_id, doctor_id, doctor_name, notes, created_at FROM tb_consultations "
                        "WHERE doctor_id = %s ORDER BY consultation_id DESC LIMIT %s", (doctor_id, int(limit)))
            return [(row["patient_id"], Consultation(row["consultation_id"], row["doctor_id"], row["doctor_name"],
                                                     row["notes"], row["created_at"])) for row in cur.fetchall()]

    def notes_written_this_month(self, doctor_id):
        """How many consultation notes this doctor wrote since the first day of this month."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tb_consultations WHERE doctor_id = %s "
                        "AND created_at >= DATE_SUB(CURDATE(), INTERVAL DAYOFMONTH(CURDATE()) - 1 DAY)", (doctor_id,))
            return cur.fetchone()["n"]

    # ---- reading ----
    def exists(self, patient_id, lock=False):
        """True if a patient with this ID exists. With lock=True the row is also held until the transaction ends, so
        two requests about the same patient cannot interleave."""
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id FROM tb_patients WHERE patient_id = %s" + (" FOR UPDATE" if lock else ""),
                        (patient_id,))
            return cur.fetchone() is not None

    def id_for_mobile(self, mobile):
        """The ID of the patient who has this mobile number (such as 09171234567), or None if nobody does. Numbers are
        unique, which is what lets a patient log in with one."""
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id FROM tb_patients WHERE mobile_number = %s", (mobile,))
            row = cur.fetchone()
            return row["patient_id"] if row else None

    def get(self, patient_id, with_record=True):
        """One patient, or None if there is no such ID."""
        return self.get_many([patient_id], with_record).get(patient_id)

    def get_many(self, patient_ids, with_record=True):
        """A dictionary {id: Patient} for the given IDs, built with a fixed number of queries however many IDs there
        are, so a long list stays fast. with_record=False skips the medical record, for lists that only show names."""
        ids = list(dict.fromkeys(patient_ids))
        if not ids:
            return {}
        marks = ", ".join(["%s"] * len(ids))
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM tb_patients WHERE patient_id IN ({marks})", ids)
            patients = {row["patient_id"]: self._build(row) for row in cur.fetchall()}
            if with_record and patients:
                self._fill_records(cur, patients, marks, list(patients))
        return patients

    @staticmethod
    def _build(row):
        """Make a Patient from one database row."""
        patient = Patient(row["patient_id"], row["name"], row["password"], row["sex"], row["date_of_birth"],
                          row["mobile_number"], row["created_year"], row["password_changed_at"], row["height_cm"],
                          row["weight_kg"], row["emergency_name"], row["emergency_relationship"], row["emergency_mobile"])
        patient.record.blood_type = row["blood_type"]
        return patient

    @classmethod
    def _fill_records(cls, cur, patients, marks, ids):
        """Add each patient's surgeries, health items and consultations. A few queries cover all the patients together, not
        a few per patient."""
        cur.execute(f"SELECT patient_id, item_name FROM tb_medical_items WHERE patient_id IN ({marks}) AND item_type = 'surgery' "
                    "ORDER BY item_id", ids)
        for row in cur.fetchall():
            patients[row["patient_id"]].record.add_surgery(row["item_name"])
        cur.execute(f"SELECT {HEALTH_COLUMNS} FROM tb_health_items WHERE patient_id IN ({marks}) ORDER BY item_id", ids)
        for row in cur.fetchall():
            getattr(patients[row["patient_id"]].record, ADDERS[row["kind"]])(cls._health_item(row))
        cur.execute("SELECT consultation_id, patient_id, doctor_id, doctor_name, notes, created_at "
                    f"FROM tb_consultations WHERE patient_id IN ({marks}) ORDER BY consultation_id", ids)
        for row in cur.fetchall():
            patients[row["patient_id"]].record.add_consultation(
                Consultation(row["consultation_id"], row["doctor_id"], row["doctor_name"], row["notes"],
                             row["created_at"]))
