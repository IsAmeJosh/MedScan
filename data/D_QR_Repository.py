"""Reads and writes the one-time secrets that go inside patients' QR codes."""
from models.M_QR_Token import QRToken


class QRRepository:
    """Reads and writes the one-time QR secrets (the tb_qr_tokens table). The secret column is unique and indexed, so
    finding the one a doctor scanned is a single lookup, however many codes have ever been made."""

    def __init__(self, db):
        """Keep the Database that every query goes through."""
        self.db = db

    @staticmethod
    def _build(row):
        """Make a QRToken from one database row. MySQL itself measured age_seconds, so the five-minute limit never
        depends on this computer's clock."""
        return QRToken(row["token_id"], row["patient_id"], row["secret"], row["age_seconds"])

    def add(self, patient_id, value):
        """Save a new secret for this patient. Returns its ID."""
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO tb_qr_tokens (patient_id, secret) VALUES (%s, %s)", (patient_id, value))
            return cur.lastrowid

    def newest_usable(self, patient_id):
        """The patient's newest secret that has not been used, replaced or run out of time, or None."""
        with self.db.cursor() as cur:
            cur.execute("SELECT token_id, patient_id, secret, TIMESTAMPDIFF(SECOND, created_at, NOW(6)) AS age_seconds "
                        "FROM tb_qr_tokens WHERE patient_id = %s AND spent_at IS NULL "
                        "AND created_at > NOW(6) - INTERVAL %s SECOND ORDER BY token_id DESC LIMIT 1",
                        (patient_id, QRToken.LIFETIME_SECONDS))
            row = cur.fetchone()
            return self._build(row) if row else None

    def retire_all(self, patient_id):
        """Stop every unused secret of this patient from working. This is what 'Make a new code' does first."""
        with self.db.cursor() as cur:
            cur.execute("UPDATE tb_qr_tokens SET spent_at = NOW(6) WHERE patient_id = %s AND spent_at IS NULL", (patient_id,))

    def spend(self, value, patient_id):
        """Use up a secret that belongs to this patient. Returns True if it worked, or False if there is no such
        secret for this patient, it was already used or replaced, or it ran out of time (a secret taken from one
        patient's code and put on another's is never used up). The row is locked while it is checked, so two doctors
        scanning the same code at the same moment cannot both get in."""
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                cur.execute("SELECT token_id FROM tb_qr_tokens WHERE secret = %s AND patient_id = %s AND spent_at IS NULL "
                            "AND created_at > NOW(6) - INTERVAL %s SECOND FOR UPDATE",
                            (value, patient_id, QRToken.LIFETIME_SECONDS))
                row = cur.fetchone()
                if not row:
                    return False
                cur.execute("UPDATE tb_qr_tokens SET spent_at = NOW(6) WHERE token_id = %s", (row["token_id"],))
                return True
