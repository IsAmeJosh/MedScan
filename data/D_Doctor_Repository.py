"""Reads and writes doctors."""
from models.M_Doctor import Doctor

COLUMNS = "doctor_id, name, password, specialty, created_year, clinic, mobile_number, password_changed_at"


class DoctorRepository:
    """The only place that writes SQL about doctors. The rest of the program asks for Doctor objects and never sees a
    query (abstraction)."""

    def __init__(self, db):
        """Keep the Database that every query goes through."""
        self.db = db

    def add(self, name, password, specialty, clinic, created_year, contact_number=""):
        """Insert a new doctor. Returns the new doctor's ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_doctors (name, password, specialty, clinic, mobile_number, created_year) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (name, password, specialty, clinic, contact_number, created_year))
            return cur.lastrowid

    def set_contact(self, doctor_id, contact_number):
        """Save the doctor's mobile number. An empty string removes it."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE tb_doctors SET mobile_number = %s WHERE doctor_id = %s", (contact_number, doctor_id))

    def get(self, doctor_id):
        """One doctor, or None if there is no such ID."""
        return self.get_many([doctor_id]).get(doctor_id)

    def get_many(self, doctor_ids):
        """A dictionary {id: Doctor} for the given IDs, built with one query."""
        ids = list(dict.fromkeys(doctor_ids))
        if not ids:
            return {}
        marks = ", ".join(["%s"] * len(ids))
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM tb_doctors WHERE doctor_id IN ({marks})", ids)
            return {row["doctor_id"]: Doctor(row["doctor_id"], row["name"], row["password"], row["specialty"],
                                           row["created_year"], row["clinic"], row["mobile_number"],
                                           row["password_changed_at"]) for row in cur.fetchall()}
