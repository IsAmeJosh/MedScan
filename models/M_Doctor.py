from models.M_User import User
from models.M_Consultation import Consultation


class Doctor(User):
    """A doctor. Inherits from User (inheritance)."""

    ID_PREFIX = "DR"
    clinic = ""  # default for doctors saved before clinics existed

    def __init__(self, user_id, name, password, specialty, created_year=None, clinic=""):
        super().__init__(user_id, name, password, "Doctor", created_year)
        self.specialty = specialty
        self.clinic = clinic  # hospital or clinic where the doctor works

    @property
    def workplace(self):
        """One readable line such as 'General Medicine at Bayanihan Family Clinic'."""
        return f"{self.specialty} at {self.clinic}" if self.clinic else self.specialty

    def add_consultation(self, patient, notes, consultation_id):
        """Create a note and file it in the patient's record (abstraction: callers do not see how).
        The ID is None until the note has been saved in the database."""
        c = Consultation(consultation_id, self.user_id, self.name, notes)
        patient.record.add_consultation(c)
        return c
