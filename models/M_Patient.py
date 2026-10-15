from datetime import date

from models.M_User import User
from models.M_Medical_Record import MedicalRecord
from models.M_QR_Code import QRCode


class Patient(User):
    """A patient. Inherits login and ID handling from User (inheritance)."""

    ID_PREFIX = "PT"

    def __init__(self, user_id, name, password, sex, date_of_birth, contact_number="", created_year=None):
        super().__init__(user_id, name, password, "Patient", created_year)
        self.sex = sex
        self.date_of_birth = date_of_birth
        self.contact_number = contact_number
        self.record = MedicalRecord(user_id)

    @property
    def age(self):
        """Age in whole years today, worked out from the date of birth (so it never goes stale)."""
        today = date.today()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def update_history(self, allergies="", surgeries="", medications="", blood_type=""):
        """Replace the medical history with the given comma-separated text."""
        self.record.replace_history(allergies, surgeries, medications, blood_type)

    def qr_code(self):
        """This patient's QR code. It holds only the display ID (PT-2026-01001), so a doctor who scans it gets
        exactly what typing the ID gives: the patient's name and a locked record until the patient approves."""
        return QRCode(self.display_id)
