"""Saves MedScan in a MySQL / MariaDB database (the one that comes with XAMPP).
Needs PyMySQL:  python -m pip install pymysql"""
import os

import pymysql

from data.D_Store import Store
from logic.L_MedScan_System import MedScanSystem
from models.M_Access_Request import AccessRequest
from models.M_Consultation import Consultation
from models.M_Doctor import Doctor
from models.M_Emergency_Log import EmergencyLog
from models.M_Notification import Notification
from models.M_Patient import Patient
from models.M_Record_View import RecordView

# One table per kind of object. Parents come first so the foreign keys can point at them.
TABLES = {
    "doctors": """
        CREATE TABLE IF NOT EXISTS doctors (
            user_id INT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            password VARCHAR(100) NOT NULL,
            specialty VARCHAR(100) NOT NULL,
            created_year INT NOT NULL
        ) ENGINE=InnoDB""",
    "patients": """
        CREATE TABLE IF NOT EXISTS patients (
            user_id INT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            password VARCHAR(100) NOT NULL,
            sex VARCHAR(20) NOT NULL,
            age INT NOT NULL,
            contact_number VARCHAR(20) NOT NULL,
            blood_type VARCHAR(5) NOT NULL,
            created_year INT NOT NULL
        ) ENGINE=InnoDB""",
    "record_items": """
        CREATE TABLE IF NOT EXISTS record_items (
            item_id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            kind ENUM('allergy', 'surgery', 'medication') NOT NULL,
            item VARCHAR(200) NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (user_id)
        ) ENGINE=InnoDB""",
    "consultations": """
        CREATE TABLE IF NOT EXISTS consultations (
            consultation_id INT PRIMARY KEY,
            patient_id INT NOT NULL,
            doctor_id INT NOT NULL,
            doctor_name VARCHAR(100) NOT NULL,
            notes TEXT NOT NULL,
            created_at DATETIME(6) NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (user_id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (user_id)
        ) ENGINE=InnoDB""",
    "access_requests": """
        CREATE TABLE IF NOT EXISTS access_requests (
            request_id INT PRIMARY KEY,
            doctor_id INT NOT NULL,
            patient_id INT NOT NULL,
            status VARCHAR(10) NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors (user_id),
            FOREIGN KEY (patient_id) REFERENCES patients (user_id)
        ) ENGINE=InnoDB""",
    "emergency_logs": """
        CREATE TABLE IF NOT EXISTS emergency_logs (
            log_id INT PRIMARY KEY,
            doctor_id INT NOT NULL,
            patient_id INT NOT NULL,
            reason TEXT NOT NULL,
            created_at DATETIME(6) NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors (user_id),
            FOREIGN KEY (patient_id) REFERENCES patients (user_id)
        ) ENGINE=InnoDB""",
    "record_views": """
        CREATE TABLE IF NOT EXISTS record_views (
            view_id INT PRIMARY KEY,
            doctor_id INT NOT NULL,
            patient_id INT NOT NULL,
            via VARCHAR(10) NOT NULL,
            created_at DATETIME(6) NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors (user_id),
            FOREIGN KEY (patient_id) REFERENCES patients (user_id)
        ) ENGINE=InnoDB""",
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INT PRIMARY KEY,
            recipient_id INT NOT NULL,
            message TEXT NOT NULL,
            related_request_id INT NULL,
            is_read TINYINT(1) NOT NULL,
            created_at DATETIME(6) NOT NULL
        ) ENGINE=InnoDB""",
}
# Children are emptied before their parents, otherwise the foreign keys would refuse.
EMPTY_ORDER = ["record_items", "consultations", "access_requests", "emergency_logs",
               "record_views", "notifications", "patients", "doctors"]


class MySQLStore(Store):
    """Keeps MedScan in real tables. save() rewrites everything inside one transaction,
    so a failed save changes nothing."""

    def __init__(self, host="127.0.0.1", port=3306, user="root", password="", database="db_medscan"):
        self.host, self.port, self.user = host, int(port), user
        self.password, self.database = password, database

    @classmethod
    def from_environment(cls):
        """Read the connection settings from MEDSCAN_DB_* variables, with XAMPP's defaults."""
        env = os.environ.get
        return cls(env("MEDSCAN_DB_HOST", "127.0.0.1"), env("MEDSCAN_DB_PORT", "3306"),
                   env("MEDSCAN_DB_USER", "root"), env("MEDSCAN_DB_PASSWORD", ""),
                   env("MEDSCAN_DB_NAME", "db_medscan"))

    def _connect(self):
        """Open a new connection (raises if MySQL is not running)."""
        return pymysql.connect(host=self.host, port=self.port, user=self.user, password=self.password,
                               database=self.database, charset="utf8mb4", connect_timeout=3)

    def check(self):
        """Raise an error unless the database can be reached."""
        self._connect().close()

    def create_tables(self, conn):
        """Create any missing tables. Safe to run every time."""
        with conn.cursor() as cur:
            for sql in TABLES.values():
                cur.execute(sql)
        conn.commit()

    # ---- load ----
    def load(self):
        """Rebuild the MedScanSystem from the tables, or return None if they are empty."""
        conn = self._connect()
        try:
            self.create_tables(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, name, password, sex, age, contact_number, blood_type, created_year "
                            "FROM patients ORDER BY user_id")
                patient_rows = cur.fetchall()
                cur.execute("SELECT user_id, name, password, specialty, created_year FROM doctors ORDER BY user_id")
                doctor_rows = cur.fetchall()
                if not patient_rows and not doctor_rows:
                    return None
                system = MedScanSystem()
                for uid, name, password, specialty, year in doctor_rows:
                    system.doctors[uid] = Doctor(uid, name, password, specialty, year)
                for uid, name, password, sex, age, contact, blood, year in patient_rows:
                    patient = Patient(uid, name, password, sex, age, contact, year)
                    patient.record.blood_type = blood
                    system.patients[uid] = patient
                self._load_record_items(cur, system)
                self._load_activity(cur, system)
            system.restore_counters()
            return system
        finally:
            conn.close()

    @staticmethod
    def _load_record_items(cur, system):
        """Put allergies, surgeries, medications and consultations back into each record."""
        adders = {"allergy": "add_allergy", "surgery": "add_surgery", "medication": "add_medication"}
        cur.execute("SELECT patient_id, kind, item FROM record_items ORDER BY item_id")
        for patient_id, kind, item in cur.fetchall():
            getattr(system.patients[patient_id].record, adders[kind])(item)
        cur.execute("SELECT consultation_id, patient_id, doctor_id, doctor_name, notes, created_at "
                    "FROM consultations ORDER BY consultation_id")
        for cid, patient_id, doctor_id, doctor_name, notes, created_at in cur.fetchall():
            system.patients[patient_id].record.add_consultation(
                Consultation(cid, doctor_id, doctor_name, notes, created_at))

    @staticmethod
    def _load_activity(cur, system):
        """Rebuild requests, emergency logs, record views and notifications."""
        cur.execute("SELECT request_id, doctor_id, patient_id, status FROM access_requests ORDER BY request_id")
        system.requests = [AccessRequest(*row) for row in cur.fetchall()]
        cur.execute("SELECT log_id, doctor_id, patient_id, reason, created_at FROM emergency_logs ORDER BY log_id")
        system.emergency_logs = [EmergencyLog(*row) for row in cur.fetchall()]
        cur.execute("SELECT view_id, doctor_id, patient_id, via, created_at FROM record_views ORDER BY view_id")
        system.record_views = [RecordView(*row) for row in cur.fetchall()]
        cur.execute("SELECT notification_id, recipient_id, message, related_request_id, is_read, created_at "
                    "FROM notifications ORDER BY notification_id")
        system.notifications = [Notification(nid, rid, message, related, bool(is_read), created_at)
                                for nid, rid, message, related, is_read, created_at in cur.fetchall()]

    # ---- save ----
    def save(self, system):
        """Empty the tables and write everything again, all in one transaction."""
        conn = self._connect()
        try:
            self.create_tables(conn)
            with conn.cursor() as cur:
                for table in EMPTY_ORDER:
                    cur.execute(f"DELETE FROM {table}")
                self._save_people(cur, system)
                self._save_activity(cur, system)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _save_people(cur, system):
        """Doctors, patients, their record items and consultations."""
        cur.executemany("INSERT INTO doctors VALUES (%s, %s, %s, %s, %s)",
                        [(d.user_id, d.name, d.credential_for_storage(), d.specialty, d.created_year)
                         for d in system.doctors.values()])
        cur.executemany("INSERT INTO patients VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        [(p.user_id, p.name, p.credential_for_storage(), p.sex, p.age, p.contact_number,
                          p.record.blood_type, p.created_year) for p in system.patients.values()])
        items, consultations = [], []
        for p in system.patients.values():
            record = p.record
            items += [(p.user_id, "allergy", x) for x in record.allergies]
            items += [(p.user_id, "surgery", x) for x in record.surgeries]
            items += [(p.user_id, "medication", x) for x in record.medications]
            consultations += [(c.consultation_id, p.user_id, c.doctor_id, c.doctor_name, c.notes, c.date)
                              for c in record.consultations]
        cur.executemany("INSERT INTO record_items (patient_id, kind, item) VALUES (%s, %s, %s)", items)
        cur.executemany("INSERT INTO consultations VALUES (%s, %s, %s, %s, %s, %s)", consultations)

    @staticmethod
    def _save_activity(cur, system):
        """Requests, emergency logs, record views and notifications."""
        cur.executemany("INSERT INTO access_requests VALUES (%s, %s, %s, %s)",
                        [(r.request_id, r.doctor_id, r.patient_id, r.status) for r in system.requests])
        cur.executemany("INSERT INTO emergency_logs VALUES (%s, %s, %s, %s, %s)",
                        [(e.log_id, e.doctor_id, e.patient_id, e.reason, e.timestamp)
                         for e in system.emergency_logs])
        cur.executemany("INSERT INTO record_views VALUES (%s, %s, %s, %s, %s)",
                        [(v.view_id, v.doctor_id, v.patient_id, v.via, v.timestamp)
                         for v in system.record_views])
        cur.executemany("INSERT INTO notifications VALUES (%s, %s, %s, %s, %s, %s)",
                        [(n.notification_id, n.recipient_id, n.message, n.related_request_id,
                          int(n.is_read), n.timestamp) for n in system.notifications])
