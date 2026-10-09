from models.M_User import User
from models.M_Medical_Record import MedicalRecord


class Patient(User):
    """A patient. Inherits login and ID handling from User (inheritance)."""

    ID_PREFIX = "PT"

    def __init__(self, user_id, name, password, sex, age, contact_number="", created_year=None):
        super().__init__(user_id, name, password, "Patient", created_year)
        self.sex = sex
        self.age = age
        self.contact_number = contact_number
        self.record = MedicalRecord(user_id)

    def update_history(self, allergies="", surgeries="", medications="", blood_type=""):
        """Replace the medical history with the given comma-separated text."""
        self.record.replace_history(allergies, surgeries, medications, blood_type)
