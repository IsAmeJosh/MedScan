"""A doctor account: a User plus a specialty and, if they have one, a clinic."""
from models.M_User import User
from models.M_Consultation import Consultation


class Doctor(User):
    """A doctor. It inherits the ID, name and password handling from User (inheritance) and adds a specialty, a clinic
    and a mobile number."""

    ID_PREFIX = "DR"
    clinic = ""  # A doctor may have no clinic, so this is the default until one is given.

    def __init__(self, user_id, name, password, specialty, created_year=None, clinic="", contact_number="",
                 password_changed_at=None):
        """Set up a doctor. The shared fields are passed up to User. The clinic and the mobile number are optional and
        stay empty when the doctor does not give them."""
        super().__init__(user_id, name, password, "Doctor", created_year, password_changed_at)
        self.specialty = specialty
        self.clinic = clinic  # The hospital or clinic where the doctor works.
        self.contact_number = contact_number  # Optional: stays "" when the doctor has not given a number.

    def add_consultation(self, patient, notes, consultation_id):
        """Write a consultation note and file it in the patient's record. The doctor only says what the note is.
        Creating the Consultation and attaching it happens here, so callers do not need to know how (abstraction).
        The note's ID is None until it has been saved in the database."""
        c = Consultation(consultation_id, self.user_id, self.name, notes)
        patient.record.add_consultation(c)
        return c
