from datetime import datetime


class Consultation:
    """One doctor-patient encounter and the notes written for it."""

    def __init__(self, consultation_id, doctor_id, doctor_name, notes, date=None):
        self.consultation_id = consultation_id
        self.doctor_id = doctor_id
        self.doctor_name = doctor_name
        self.notes = notes
        self.date = date or datetime.now()

    def summary(self):
        """One readable line: date, doctor and notes."""
        return f"{self.date:%Y-%m-%d %H:%M} - Dr. {self.doctor_name}: {self.notes}"