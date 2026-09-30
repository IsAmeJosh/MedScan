from MS_User import User
from MS_Medical_Record import MedicalRecord


class Patient(User):
    def __init__(self, user_id, name, password, sex, age):
        super().__init__(user_id, name, password, "Patient")
        self.sex = sex
        self.age = age
        self.record = MedicalRecord(user_id)

    def update_history(self, allergies="", surgeries=""):
        for a in allergies.split(","):
            self.record.add_allergy(a.strip())
        for s in surgeries.split(","):
            self.record.add_surgery(s.strip())