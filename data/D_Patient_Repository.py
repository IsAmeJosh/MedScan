"""Reads and writes patients, their medical record items and their consultation notes."""
import pymysql

from models.M_Consultation import Consultation
from models.M_Patient import Patient

DUPLICATE_KEY = 1062  # MySQL's error number for "that value is already used"
MOBILE_TAKEN = "That mobile number is already used by another account."
COLUMNS = "patient_id, name, password, sex, date_of_birth, mobile_number, blood_type, created_year, password_changed_at"
ADDERS = {"allergy": "add_allergy", "surgery": "add_surgery", "medication": "add_medication"}


class PatientRepository:
    """The only place that writes SQL about patients and their medical records (allergies, surgeries, medications and
    consultation notes). The rest of the program asks for Patient objects and never sees a query (abstraction).
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
                self._write_items(patient_id, record)
        except pymysql.err.IntegrityError as error:  # Someone else saved this mobile number at the very same moment.
            if error.args[0] == DUPLICATE_KEY:
                raise ValueError(MOBILE_TAKEN) from error
            raise
        return patient_id

    def update_info(self, patient_id, contact_number, record):
        """Replace the patient's mobile number, blood type and the allergy, surgery and medication lists in one go."""
        try:
            with self.db.unit_of_work():
                with self.db.cursor() as cur:
                    cur.execute("UPDATE tb_patients SET mobile_number = %s, blood_type = %s WHERE patient_id = %s",
                                (contact_number, record.blood_type, patient_id))
                self._write_items(patient_id, record)
        except pymysql.err.IntegrityError as error:
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

    def _write_items(self, patient_id, record):
        """Rewrite the patient's allergy, surgery and medication rows from the record, so the table always matches
        what the record holds."""
        rows = ([(patient_id, "allergy", x) for x in record.allergies]
                + [(patient_id, "surgery", x) for x in record.surgeries]
                + [(patient_id, "medication", x) for x in record.medications])
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM tb_medical_items WHERE patient_id = %s", (patient_id,))
            if rows:
                cur.executemany("INSERT INTO tb_medical_items (patient_id, item_type, item_name) VALUES (%s, %s, %s)", rows)

    def add_consultation(self, patient_id, consultation):
        """Save a consultation note. Returns the new note's ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_consultations (patient_id, doctor_id, doctor_name, notes) "
                        "VALUES (%s, %s, %s, %s)",
                        (patient_id, consultation.doctor_id, consultation.doctor_name, consultation.notes))
            return cur.lastrowid

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
                          row["mobile_number"], row["created_year"], row["password_changed_at"])
        patient.record.blood_type = row["blood_type"]
        return patient

    @staticmethod
    def _fill_records(cur, patients, marks, ids):
        """Add each patient's list items and consultations. Two queries cover all the patients together, not two per
        patient."""
        cur.execute(f"SELECT patient_id, item_type, item_name FROM tb_medical_items WHERE patient_id IN ({marks}) "
                    "ORDER BY item_id", ids)
        for row in cur.fetchall():
            getattr(patients[row["patient_id"]].record, ADDERS[row["item_type"]])(row["item_name"])
        cur.execute("SELECT consultation_id, patient_id, doctor_id, doctor_name, notes, created_at "
                    f"FROM tb_consultations WHERE patient_id IN ({marks}) ORDER BY consultation_id", ids)
        for row in cur.fetchall():
            patients[row["patient_id"]].record.add_consultation(
                Consultation(row["consultation_id"], row["doctor_id"], row["doctor_name"], row["notes"],
                             row["created_at"]))
