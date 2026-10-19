"""A patient account: a User plus the details only a patient has."""
from datetime import date

from models.M_User import User
from models.M_Medical_Record import MedicalRecord
from models.M_QR_Code import QRCode


class Patient(User):
    """A patient. It inherits the ID, name and password handling from User (inheritance) and adds a sex, a date of
    birth, a mobile number, a medical record and a QR code."""

    ID_PREFIX = "PT"

    def __init__(self, user_id, name, password, sex, date_of_birth, contact_number="", created_year=None,
                 password_changed_at=None, height_cm=None, weight_kg=None, emergency_name="", emergency_relationship="",
                 emergency_mobile=""):
        """Set up a patient. The shared fields are passed up to User and the rest belong to the patient.
        The medical record starts empty and fills in as the patient or a doctor adds to it. Height (cm), weight (kg)
        and the emergency contact are optional: None or a blank means the patient has not added them."""
        super().__init__(user_id, name, password, "Patient", created_year, password_changed_at)
        self.sex = sex
        self.date_of_birth = date_of_birth
        self.contact_number = contact_number
        self.height_cm = height_cm
        self.weight_kg = weight_kg
        self.emergency_name = emergency_name
        self.emergency_relationship = emergency_relationship
        self.emergency_mobile = emergency_mobile
        self.record = MedicalRecord(user_id)

    @property
    def has_emergency_contact(self):
        """True when the patient has added any part of an emergency contact (name, relationship or mobile)."""
        return bool(self.emergency_name or self.emergency_relationship or self.emergency_mobile)

    @property
    def age(self):
        """The patient's age in whole years today. It is worked out from the date of birth every time it is asked for,
        so it never goes out of date (a stored age would)."""
        today = date.today()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def update_history(self, allergies="", surgeries="", medications="", blood_type=""):
        """Replace the whole medical history from comma-separated text such as 'Penicillin, Peanuts'. The record does
        the splitting and tidying."""
        self.record.replace_history(allergies, surgeries, medications, blood_type)

    def qr_code(self, token=None):
        """This patient's QR code, ready to draw. Given a QRToken it is the live code: the display ID plus the
        one-time secret, and showing it to a doctor in person is the patient's approval. Without a token it holds
        only the display ID (PT-2026-01001), which just finds the patient and approves nothing. Either way it never
        contains health information."""
        if token is None:
            return QRCode(self.display_id)
        return QRCode.with_secret(self.display_id, token.value)
