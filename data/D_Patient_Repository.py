import pymysql

from models.M_Consultation import Consultation
from models.M_Patient import Patient

DUPLICATE_KEY = 1062  # MySQL's error number for "that value is already used"
MOBILE_TAKEN = "That mobile number is already used by another account."
COLUMNS = "user_id, name, password, sex, date_of_birth, contact_number, blood_type, created_year"
ADDERS = {"allergy": "add_allergy", "surgery": "add_surgery", "medication": "add_medication"}


class PatientRepository:
    """Reads and writes patients together with their medical record (allergies, surgeries, medications,
    consultations). Every method is one or a few targeted SQL statements."""

    def __init__(self, db):
        self.db = db

    # ---- writing ----
    def add(self, name, password, sex, date_of_birth, contact_number, created_year, record):
        """Insert a new patient with their starting record. Returns the new ID."""
        try:
            with self.db.unit_of_work():
                with self.db.cursor() as cur:
                    cur.execute("INSERT INTO patients (name, password, sex, date_of_birth, contact_number, "
                                "blood_type, created_year) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (name, password, sex, date_of_birth, contact_number, record.blood_type, created_year))
                    patient_id = cur.lastrowid
                self._write_items(patient_id, record)
        except pymysql.err.IntegrityError as error:  # two people took the same number at the same moment
            if error.args[0] == DUPLICATE_KEY:
                raise ValueError(MOBILE_TAKEN) from error
            raise
        return patient_id

    def update_info(self, patient_id, contact_number, record):
        """Replace the patient's mobile number, blood type and allergy, surgery and medication lists."""
        try:
            with self.db.unit_of_work():
                with self.db.cursor() as cur:
                    cur.execute("UPDATE patients SET contact_number = %s, blood_type = %s WHERE user_id = %s",
                                (contact_number, record.blood_type, patient_id))
                self._write_items(patient_id, record)
        except pymysql.err.IntegrityError as error:
            if error.args[0] == DUPLICATE_KEY:
                raise ValueError(MOBILE_TAKEN) from error
            raise

    def _write_items(self, patient_id, record):
        """Rewrite the patient's allergy, surgery and medication rows from the record."""
        rows = ([(patient_id, "allergy", x) for x in record.allergies]
                + [(patient_id, "surgery", x) for x in record.surgeries]
                + [(patient_id, "medication", x) for x in record.medications])
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM record_items WHERE patient_id = %s", (patient_id,))
            if rows:
                cur.executemany("INSERT INTO record_items (patient_id, kind, item) VALUES (%s, %s, %s)", rows)

    def add_consultation(self, patient_id, consultation):
        """Save a consultation. Returns its new ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO consultations (patient_id, doctor_id, doctor_name, notes) "
                        "VALUES (%s, %s, %s, %s)",
                        (patient_id, consultation.doctor_id, consultation.doctor_name, consultation.notes))
            return cur.lastrowid

    # ---- reading ----
    def exists(self, patient_id, lock=False):
        """True if the patient exists. lock=True also holds the row until the transaction ends,
        so two requests about the same patient cannot interleave."""
        with self.db.cursor() as cur:
            cur.execute("SELECT user_id FROM patients WHERE user_id = %s" + (" FOR UPDATE" if lock else ""),
                        (patient_id,))
            return cur.fetchone() is not None

    def id_for_mobile(self, mobile):
        """The ID of the patient who has this mobile number (09171234567), or None."""
        with self.db.cursor() as cur:
            cur.execute("SELECT user_id FROM patients WHERE contact_number = %s", (mobile,))
            row = cur.fetchone()
            return row["user_id"] if row else None

    def get(self, patient_id, with_record=True):
        """One patient, or None."""
        return self.get_many([patient_id], with_record).get(patient_id)

    def get_many(self, patient_ids, with_record=True):
        """{id: Patient} for the given IDs in a fixed number of queries.
        with_record=False skips the medical record (the Patient then has an empty one), for lists that
        only show names."""
        ids = list(dict.fromkeys(patient_ids))
        if not ids:
            return {}
        marks = ", ".join(["%s"] * len(ids))
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM patients WHERE user_id IN ({marks})", ids)
            patients = {row["user_id"]: self._build(row) for row in cur.fetchall()}
            if with_record and patients:
                self._fill_records(cur, patients, marks, list(patients))
        return patients

    @staticmethod
    def _build(row):
        """A Patient from one database row."""
        patient = Patient(row["user_id"], row["name"], row["password"], row["sex"], row["date_of_birth"],
                          row["contact_number"], row["created_year"])
        patient.record.blood_type = row["blood_type"]
        return patient

    @staticmethod
    def _fill_records(cur, patients, marks, ids):
        """Add each patient's list items and consultations (two queries for all patients together)."""
        cur.execute(f"SELECT patient_id, kind, item FROM record_items WHERE patient_id IN ({marks}) "
                    "ORDER BY item_id", ids)
        for row in cur.fetchall():
            getattr(patients[row["patient_id"]].record, ADDERS[row["kind"]])(row["item"])
        cur.execute("SELECT consultation_id, patient_id, doctor_id, doctor_name, notes, created_at "
                    f"FROM consultations WHERE patient_id IN ({marks}) ORDER BY consultation_id", ids)
        for row in cur.fetchall():
            patients[row["patient_id"]].record.add_consultation(
                Consultation(row["consultation_id"], row["doctor_id"], row["doctor_name"], row["notes"],
                             row["created_at"]))

    def consultation_days_for_doctor(self, doctor_id, days):
        """{date: number of notes} for the notes this doctor wrote in the last `days` days (today included)."""
        with self.db.cursor() as cur:
            cur.execute("SELECT DATE(created_at) AS day, COUNT(*) AS n FROM consultations "
                        "WHERE doctor_id = %s AND created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) GROUP BY day",
                        (doctor_id, days - 1))
            return {row["day"]: row["n"] for row in cur.fetchall()}

    def consultation_count_for_doctor(self, doctor_id):
        """How many notes this doctor has written."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM consultations WHERE doctor_id = %s", (doctor_id,))
            return cur.fetchone()["n"]
