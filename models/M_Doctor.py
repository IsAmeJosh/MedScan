from models.M_User import User
from models.M_Consultation import Consultation


class Doctor(User):
    _next_consultation = 1

    def __init__(self, user_id, name, password, specialty):
        super().__init__(user_id, name, password, "Doctor")
        self.specialty = specialty

    def add_consultation(self, patient, notes):
        c = Consultation(Doctor._next_consultation, self.user_id, self.name, notes)
        Doctor._next_consultation += 1
        patient.record.add_consultation(c)
        return c