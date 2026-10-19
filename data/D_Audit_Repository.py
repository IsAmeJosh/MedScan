"""Reads and writes the audit trail: record views, emergency openings and QR scans."""
from models.M_Emergency_Log import EmergencyLog
from models.M_Health_Change import HealthChange
from models.M_QR_Scan import QRScan
from models.M_Record_View import RecordView


class AuditRepository:
    """The only place that writes SQL about the audit trail: emergency overrides, QR scans and every time a record was
    opened. Entries are only ever added, never changed or deleted, so the trail can be trusted."""

    def __init__(self, db):
        """Keep the Database that every query goes through."""
        self.db = db

    # ---- emergency overrides ----
    @staticmethod
    def _emergency(row):
        """Make an EmergencyLog from one database row."""
        return EmergencyLog(row["log_id"], row["doctor_id"], row["patient_id"], row["reason"], row["created_at"])

    def add_emergency(self, doctor_id, patient_id, reason):
        """Record an emergency override. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_emergency_logs (doctor_id, patient_id, reason) VALUES (%s, %s, %s)",
                        (doctor_id, patient_id, reason))
            return cur.lastrowid

    def emergencies_for_patient(self, patient_id):
        """Emergency overrides on this patient's record, newest first."""
        return self._emergencies("patient_id", patient_id)

    def emergencies_for_doctor(self, doctor_id):
        """Emergency overrides this doctor has used, newest first."""
        return self._emergencies("doctor_id", doctor_id)

    def _emergencies(self, column, value):
        """Emergency logs filtered by one column. The column name is fixed by the two methods above and is never user
        input."""
        with self.db.cursor() as cur:
            cur.execute("SELECT log_id, doctor_id, patient_id, reason, created_at FROM tb_emergency_logs "
                        f"WHERE {column} = %s ORDER BY log_id DESC", (value,))
            return [self._emergency(row) for row in cur.fetchall()]

    def emergency_active(self, doctor_id, patient_id, hours):
        """True if this doctor used an emergency override on this patient within the last `hours` hours. After that
        the access ends by itself."""
        with self.db.cursor() as cur:
            cur.execute("SELECT 1 FROM tb_emergency_logs WHERE doctor_id = %s AND patient_id = %s "
                        "AND created_at > NOW(6) - INTERVAL %s HOUR LIMIT 1", (doctor_id, patient_id, hours))
            return cur.fetchone() is not None

    # ---- changes a doctor made to a patient's health details ----
    def add_health_change(self, doctor_id, patient_id, action, kind, item_name):
        """Record that a doctor added, changed or removed an item (action is added, changed or removed). Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_health_log (doctor_id, patient_id, action, kind, item_name) VALUES (%s, %s, %s, %s, %s)",
                        (doctor_id, patient_id, action, kind, item_name))
            return cur.lastrowid

    def health_changes_for_patient(self, patient_id):
        """Everything doctors changed in this patient's health details, newest first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT log_id, doctor_id, patient_id, action, kind, item_name, created_at FROM tb_health_log "
                        "WHERE patient_id = %s ORDER BY log_id DESC", (patient_id,))
            return [HealthChange(row["log_id"], row["doctor_id"], row["patient_id"], row["action"], row["kind"], row["item_name"],
                                 row["created_at"]) for row in cur.fetchall()]

    # ---- QR scans ----
    def add_scan(self, doctor_id, patient_id):
        """Record that a doctor scanned a patient's QR code. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_qr_scans (doctor_id, patient_id) VALUES (%s, %s)", (doctor_id, patient_id))
            return cur.lastrowid

    def scans_for_patient(self, patient_id):
        """Every time a doctor scanned this patient's code, newest first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT scan_id, doctor_id, patient_id, created_at FROM tb_qr_scans "
                        "WHERE patient_id = %s ORDER BY scan_id DESC", (patient_id,))
            return [QRScan(row["scan_id"], row["doctor_id"], row["patient_id"], row["created_at"])
                    for row in cur.fetchall()]

    # ---- record views ----
    @staticmethod
    def _view(row):
        """Make a RecordView from one database row."""
        return RecordView(row["view_id"], row["doctor_id"], row["patient_id"], row["via"], row["created_at"])

    def log_view(self, doctor_id, patient_id, via, quiet_minutes):
        """Log that a doctor opened a record, unless the same doctor already opened it the same way within the last
        `quiet_minutes` minutes. That quiet period stops someone refreshing a page from filling the history.
        Returns True if a new entry was written."""
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                cur.execute("SELECT via, TIMESTAMPDIFF(SECOND, created_at, NOW(6)) AS age FROM tb_record_views "
                            "WHERE doctor_id = %s AND patient_id = %s ORDER BY view_id DESC LIMIT 1",
                            (doctor_id, patient_id))
                last = cur.fetchone()
                if last and last["via"] == via and last["age"] < quiet_minutes * 60:
                    return False
                cur.execute("INSERT INTO tb_record_views (doctor_id, patient_id, via) VALUES (%s, %s, %s)",
                            (doctor_id, patient_id, via))
                return True

    def recent_views_for_doctor(self, doctor_id, limit):
        """A list of (patient ID, when it was last opened) for the records this doctor opened most recently, newest
        first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id, MAX(view_id) AS latest, MAX(created_at) AS last_opened FROM tb_record_views "
                        "WHERE doctor_id = %s GROUP BY patient_id ORDER BY latest DESC LIMIT %s", (doctor_id, int(limit)))
            return [(row["patient_id"], row["last_opened"]) for row in cur.fetchall()]

    def views_for_patient(self, patient_id):
        """Every time a doctor opened this patient's record, newest first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT view_id, doctor_id, patient_id, via, created_at FROM tb_record_views "
                        "WHERE patient_id = %s ORDER BY view_id DESC", (patient_id,))
            return [self._view(row) for row in cur.fetchall()]

    def scans_for_doctor(self, doctor_id, limit):
        """A list of (patient ID, when) for the patients this doctor scanned most recently, one line per patient (the
        latest scan), newest first."""
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id, MAX(scan_id) AS latest, MAX(created_at) AS last_scanned FROM tb_qr_scans "
                        "WHERE doctor_id = %s GROUP BY patient_id ORDER BY latest DESC LIMIT %s", (doctor_id, int(limit)))
            return [(row["patient_id"], row["last_scanned"]) for row in cur.fetchall()]

    def counts_this_month(self, doctor_id):
        """What this doctor did since the first day of this month, as {'patients': how many different records they
        opened, 'scans': QR scans, 'emergencies': emergency overrides}."""
        since = "created_at >= DATE_SUB(CURDATE(), INTERVAL DAYOFMONTH(CURDATE()) - 1 DAY)"
        with self.db.cursor() as cur:
            cur.execute(f"SELECT COUNT(DISTINCT patient_id) AS n FROM tb_record_views WHERE doctor_id = %s AND {since}", (doctor_id,))
            patients = cur.fetchone()["n"]
            cur.execute(f"SELECT COUNT(*) AS n FROM tb_qr_scans WHERE doctor_id = %s AND {since}", (doctor_id,))
            scans = cur.fetchone()["n"]
            cur.execute(f"SELECT COUNT(*) AS n FROM tb_emergency_logs WHERE doctor_id = %s AND {since}", (doctor_id,))
            emergencies = cur.fetchone()["n"]
        return {"patients": patients, "scans": scans, "emergencies": emergencies}

    def last_views_by_doctor(self, patient_id):
        """A dictionary {doctor_id: newest RecordView} for everyone who has opened this patient's record."""
        with self.db.cursor() as cur:
            cur.execute("SELECT v.view_id, v.doctor_id, v.patient_id, v.via, v.created_at FROM tb_record_views v "
                        "JOIN (SELECT doctor_id, MAX(view_id) AS newest FROM tb_record_views "
                        "WHERE patient_id = %s GROUP BY doctor_id) latest ON latest.newest = v.view_id", (patient_id,))
            return {row["doctor_id"]: self._view(row) for row in cur.fetchall()}
