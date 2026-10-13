from models.M_Access_Request import AccessRequest


class AccessRepository:
    """Reads and writes access requests (a doctor asking a patient for access)."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _build(row):
        """An AccessRequest from one database row."""
        return AccessRequest(row["request_id"], row["doctor_id"], row["patient_id"], row["status"])

    def _list(self, where, params, newest_first):
        """All requests matching a WHERE clause, in order."""
        order = "DESC" if newest_first else "ASC"
        with self.db.cursor() as cur:
            cur.execute("SELECT request_id, doctor_id, patient_id, status FROM access_requests "
                        f"WHERE {where} ORDER BY request_id {order}", params)
            return [self._build(row) for row in cur.fetchall()]

    def add(self, doctor_id, patient_id):
        """Insert a new Pending request. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO access_requests (doctor_id, patient_id) VALUES (%s, %s)",
                        (doctor_id, patient_id))
            return cur.lastrowid

    def get(self, request_id, lock=False):
        """One request, or None. lock=True holds the row until the transaction ends."""
        with self.db.cursor() as cur:
            cur.execute("SELECT request_id, doctor_id, patient_id, status FROM access_requests "
                        "WHERE request_id = %s" + (" FOR UPDATE" if lock else ""), (request_id,))
            row = cur.fetchone()
            return self._build(row) if row else None

    def set_status(self, request_id, status):
        """Change a request to Approved, Denied or Revoked."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE access_requests SET status = %s WHERE request_id = %s", (status, request_id))

    def history(self, doctor_id, patient_id):
        """Every request between this doctor and patient, oldest first."""
        return self._list("doctor_id = %s AND patient_id = %s", (doctor_id, patient_id), newest_first=False)

    def for_patient(self, patient_id):
        """Every request addressed to this patient, newest first."""
        return self._list("patient_id = %s", (patient_id,), newest_first=True)

    def for_doctor(self, doctor_id, status=None):
        """Every request this doctor has sent, newest first (only those in `status`, if given)."""
        if status:
            return self._list("doctor_id = %s AND status = %s", (doctor_id, status), newest_first=True)
        return self._list("doctor_id = %s", (doctor_id,), newest_first=True)

    def has_approved(self, doctor_id, patient_id):
        """True if this doctor currently has the patient's approval."""
        with self.db.cursor() as cur:
            cur.execute("SELECT 1 FROM access_requests WHERE doctor_id = %s AND patient_id = %s "
                        "AND status = 'Approved' LIMIT 1", (doctor_id, patient_id))
            return cur.fetchone() is not None

    def pending_count_for_patient(self, patient_id):
        """How many requests are waiting for this patient's answer."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM access_requests WHERE patient_id = %s AND status = 'Pending'",
                        (patient_id,))
            return cur.fetchone()["n"]

    def summary_for_doctor(self, doctor_id):
        """{'pending': n, 'approved': n, 'denied': n, 'revoked': n} for this doctor's requests."""
        summary = {"pending": 0, "approved": 0, "denied": 0, "revoked": 0}
        with self.db.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) AS n FROM access_requests WHERE doctor_id = %s GROUP BY status",
                        (doctor_id,))
            for row in cur.fetchall():
                summary[row["status"].lower()] = row["n"]
        return summary

    def pending_request_ids_for_patient(self, patient_id):
        """IDs of the requests waiting for this patient's answer."""
        with self.db.cursor() as cur:
            cur.execute("SELECT request_id FROM access_requests WHERE patient_id = %s AND status = 'Pending' "
                        "ORDER BY request_id", (patient_id,))
            return [row["request_id"] for row in cur.fetchall()]

    def unopened_approved_patient_ids(self, doctor_id):
        """IDs of patients who approved this doctor and whose record this doctor has never opened."""
        with self.db.cursor() as cur:
            cur.execute("SELECT DISTINCT r.patient_id FROM access_requests r WHERE r.doctor_id = %s "
                        "AND r.status = 'Approved' AND NOT EXISTS (SELECT 1 FROM record_views v "
                        "WHERE v.doctor_id = r.doctor_id AND v.patient_id = r.patient_id) ORDER BY r.patient_id",
                        (doctor_id,))
            return [row["patient_id"] for row in cur.fetchall()]

    def approved_patient_ids(self, doctor_id):
        """IDs of the patients who currently approve this doctor, in ID order."""
        with self.db.cursor() as cur:
            cur.execute("SELECT DISTINCT patient_id FROM access_requests WHERE doctor_id = %s "
                        "AND status = 'Approved' ORDER BY patient_id", (doctor_id,))
            return [row["patient_id"] for row in cur.fetchall()]
