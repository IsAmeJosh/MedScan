from models.M_Doctor import Doctor

COLUMNS = "user_id, name, password, specialty, created_year, clinic"


class DoctorRepository:
    """Reads and writes doctors."""

    def __init__(self, db):
        self.db = db

    def add(self, name, password, specialty, clinic, created_year):
        """Insert a new doctor. Returns the new ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO doctors (name, password, specialty, clinic, created_year) "
                        "VALUES (%s, %s, %s, %s, %s)", (name, password, specialty, clinic, created_year))
            return cur.lastrowid

    def get(self, doctor_id):
        """One doctor, or None."""
        return self.get_many([doctor_id]).get(doctor_id)

    def get_many(self, doctor_ids):
        """{id: Doctor} for the given IDs, in one query."""
        ids = list(dict.fromkeys(doctor_ids))
        if not ids:
            return {}
        marks = ", ".join(["%s"] * len(ids))
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM doctors WHERE user_id IN ({marks})", ids)
            return {row["user_id"]: Doctor(row["user_id"], row["name"], row["password"], row["specialty"],
                                           row["created_year"], row["clinic"]) for row in cur.fetchall()}
