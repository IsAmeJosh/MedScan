from models.M_Emergency_Log import EmergencyLog
from models.M_Record_View import RecordView


class AuditRepository:
    """Reads and writes the audit trail: emergency overrides and every time a record was opened."""

    def __init__(self, db):
        self.db = db

    # ---- emergency overrides ----
    @staticmethod
    def _emergency(row):
        """An EmergencyLog from one database row."""
        return EmergencyLog(row["log_id"], row["doctor_id"], row["patient_id"], row["reason"], row["created_at"])

    def add_emergency(self, doctor_id, patient_id, reason):
        """Record an emergency override. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO emergency_logs (doctor_id, patient_id, reason) VALUES (%s, %s, %s)",
                        (doctor_id, patient_id, reason))
            return cur.lastrowid

    def emergencies_for_patient(self, patient_id):
        """Emergency overrides on this patient's record, newest first."""
        return self._emergencies("patient_id", patient_id)

    def emergencies_for_doctor(self, doctor_id):
        """Emergency overrides by this doctor, newest first."""
        return self._emergencies("doctor_id", doctor_id)

    def _emergencies(self, column, value):
        """Emergency logs filtered by one column (a fixed name chosen above, never user input)."""
        with self.db.cursor() as cur:
            cur.execute("SELECT log_id, doctor_id, patient_id, reason, created_at FROM emergency_logs "
                        f"WHERE {column} = %s ORDER BY log_id DESC", (value,))
            return [self._emergency(row) for row in cur.fetchall()]

    def emergency_active(self, doctor_id, patient_id, hours):
        """True if this doctor opened an emergency override on this patient within the last `hours` hours."""
        with self.db.cursor() as cur:
            cur.execute("SELECT 1 FROM emergency_logs WHERE doctor_id = %s AND patient_id = %s "
                        "AND created_at > NOW(6) - INTERVAL %s HOUR LIMIT 1", (doctor_id, patient_id, hours))
            return cur.fetchone() is not None

    def emergency_count(self, doctor_id):
        """How many emergency overrides this doctor has used."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM emergency_logs WHERE doctor_id = %s", (doctor_id,))
            return cur.fetchone()["n"]

    # ---- record views ----
    @staticmethod
    def _view(row):
        """A RecordView from one database row."""
        return RecordView(row["view_id"], row["doctor_id"], row["patient_id"], row["via"], row["created_at"])

    def log_view(self, doctor_id, patient_id, via, quiet_minutes):
        """Log that a doctor opened a record, unless the same doctor already opened it the same way within
        the last `quiet_minutes` minutes. Returns True if a new entry was written."""
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                cur.execute("SELECT via, TIMESTAMPDIFF(SECOND, created_at, NOW(6)) AS age FROM record_views "
                            "WHERE doctor_id = %s AND patient_id = %s ORDER BY view_id DESC LIMIT 1",
                            (doctor_id, patient_id))
                last = cur.fetchone()
                if last and last["via"] == via and last["age"] < quiet_minutes * 60:
                    return False
                cur.execute("INSERT INTO record_views (doctor_id, patient_id, via) VALUES (%s, %s, %s)",
                            (doctor_id, patient_id, via))
                return True

    def recent_patient_ids_for_doctor(self, doctor_id, limit):
        """IDs of the patients whose records this doctor opened most recently (each once, newest first)."""
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id, MAX(view_id) AS latest FROM record_views WHERE doctor_id = %s "
                        "GROUP BY patient_id ORDER BY latest DESC LIMIT %s", (doctor_id, int(limit)))
            return [row["patient_id"] for row in cur.fetchall()]

    def views_for_patient(self, patient_id):
        """Every time a doctor opened this patient's record, newest first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT view_id, doctor_id, patient_id, via, created_at FROM record_views "
                        "WHERE patient_id = %s ORDER BY view_id DESC", (patient_id,))
            return [self._view(row) for row in cur.fetchall()]

    def last_views_by_doctor(self, patient_id):
        """{doctor_id: newest RecordView} for everyone who opened this patient's record."""
        with self.db.cursor() as cur:
            cur.execute("SELECT v.view_id, v.doctor_id, v.patient_id, v.via, v.created_at FROM record_views v "
                        "JOIN (SELECT doctor_id, MAX(view_id) AS newest FROM record_views "
                        "WHERE patient_id = %s GROUP BY doctor_id) latest ON latest.newest = v.view_id", (patient_id,))
            return {row["doctor_id"]: self._view(row) for row in cur.fetchall()}
