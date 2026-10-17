"""Reads and writes access requests: who asked to see whose record, and how it was answered."""
from models.M_Access_Request import AccessRequest

COLUMNS = "request_id, doctor_id, patient_id, status, created_at, decided_at, via"


class AccessRepository:
    """The only place that writes SQL about access requests: a doctor asking a patient to see their record, and the
    answer. The rest of the program asks for AccessRequest objects and never sees a query (abstraction)."""

    def __init__(self, db):
        """Keep the Database that every query goes through."""
        self.db = db

    @staticmethod
    def _build(row):
        """Make an AccessRequest from one database row."""
        return AccessRequest(row["request_id"], row["doctor_id"], row["patient_id"], row["status"],
                             row["created_at"], row["decided_at"], row["via"])

    def _list(self, where, params, newest_first):
        """All requests matching a WHERE clause, newest first or oldest first. It is a helper for the public methods
        below."""
        order = "DESC" if newest_first else "ASC"
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM tb_access_requests WHERE {where} ORDER BY request_id {order}", params)
            return [self._build(row) for row in cur.fetchall()]

    def add(self, doctor_id, patient_id):
        """Insert a new request that starts as Pending. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_access_requests (doctor_id, patient_id) VALUES (%s, %s)",
                        (doctor_id, patient_id))
            return cur.lastrowid

    def add_approved_by_qr(self, doctor_id, patient_id):
        """Insert a request that is already Approved, because the patient showed their one-time QR code in person.
        Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_access_requests (doctor_id, patient_id, status, decided_at, via) "
                        "VALUES (%s, %s, 'Approved', NOW(6), 'qr')", (doctor_id, patient_id))
            return cur.lastrowid

    def get(self, request_id, lock=False):
        """One request, or None. With lock=True the row is held until the transaction ends, so a request cannot be
        answered twice at once."""
        with self.db.cursor() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM tb_access_requests WHERE request_id = %s" + (" FOR UPDATE" if lock else ""),
                        (request_id,))
            row = cur.fetchone()
            return self._build(row) if row else None

    def set_status(self, request_id, status, via="request"):
        """Change a request to Approved, Denied or Revoked, and record when it happened and, for an approval, how (by
        request or by QR)."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE tb_access_requests SET status = %s, decided_at = NOW(6), via = %s WHERE request_id = %s",
                        (status, via, request_id))

    def history(self, doctor_id, patient_id):
        """Every request between this doctor and this patient, oldest first."""
        return self._list("doctor_id = %s AND patient_id = %s", (doctor_id, patient_id), newest_first=False)

    def for_patient(self, patient_id):
        """Every request addressed to this patient, newest first."""
        return self._list("patient_id = %s", (patient_id,), newest_first=True)

    def for_doctor(self, doctor_id, status=None):
        """Every request this doctor has sent, newest first. If status is given, only the requests in that state."""
        if status:
            return self._list("doctor_id = %s AND status = %s", (doctor_id, status), newest_first=True)
        return self._list("doctor_id = %s", (doctor_id,), newest_first=True)

    def has_approved(self, doctor_id, patient_id):
        """True if this doctor currently has the patient's approval."""
        with self.db.cursor() as cur:
            cur.execute("SELECT 1 FROM tb_access_requests WHERE doctor_id = %s AND patient_id = %s "
                        "AND status = 'Approved' LIMIT 1", (doctor_id, patient_id))
            return cur.fetchone() is not None

    def pending_count_for_patient(self, patient_id):
        """How many requests are waiting for this patient's answer. This is the number behind the red mark on the
        Access item."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tb_access_requests WHERE patient_id = %s AND status = 'Pending'",
                        (patient_id,))
            return cur.fetchone()["n"]

    def pending_request_ids_for_patient(self, patient_id):
        """The IDs of the requests waiting for this patient's answer."""
        with self.db.cursor() as cur:
            cur.execute("SELECT request_id FROM tb_access_requests WHERE patient_id = %s AND status = 'Pending' "
                        "ORDER BY request_id", (patient_id,))
            return [row["request_id"] for row in cur.fetchall()]

    def unopened_approved_patient_ids(self, doctor_id):
        """The IDs of patients who approved this doctor but whose record the doctor has not opened yet. This is the
        number on the doctor's Patients item."""
        with self.db.cursor() as cur:
            cur.execute("SELECT DISTINCT r.patient_id FROM tb_access_requests r WHERE r.doctor_id = %s "
                        "AND r.status = 'Approved' AND NOT EXISTS (SELECT 1 FROM tb_record_views v "
                        "WHERE v.doctor_id = r.doctor_id AND v.patient_id = r.patient_id) ORDER BY r.patient_id",
                        (doctor_id,))
            return [row["patient_id"] for row in cur.fetchall()]

    def approved_patient_ids(self, doctor_id):
        """The IDs of the patients who currently approve this doctor, in ID order."""
        with self.db.cursor() as cur:
            cur.execute("SELECT DISTINCT patient_id FROM tb_access_requests WHERE doctor_id = %s "
                        "AND status = 'Approved' ORDER BY patient_id", (doctor_id,))
            return [row["patient_id"] for row in cur.fetchall()]
