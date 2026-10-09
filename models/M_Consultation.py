from datetime import datetime


class Consultation:
    """One doctor-patient encounter and the notes written for it."""

    def __init__(self, consultation_id, doctor_id, doctor_name, notes):
        self.consultation_id = consultation_id
        self.doctor_id = doctor_id
        self.doctor_name = doctor_name
        self.notes = notes
        self.date = datetime.now()

    def summary(self):
        return f"{self.date:%Y-%m-%d %H:%M} - Dr. {self.doctor_name}: {self.notes}"