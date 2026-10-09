from models.M_User import User
from models.M_Consultation import Consultation


class Doctor(User):
    """A doctor. Inherits from User (inheritance)."""

    ID_PREFIX = "DR"

    def __init__(self, user_id, name, password, specialty, created_year=None):
        super().__init__(user_id, name, password, "Doctor", created_year)
        self.specialty = specialty

    def add_consultation(self, patient, notes, consultation_id):
        """Create a note and attach it to the patient's record (abstraction: callers do not see how)."""
        c = Consultation(consultation_id, self.user_id, self.name, notes)
        patient.record.add_consultation(c)
        return c
