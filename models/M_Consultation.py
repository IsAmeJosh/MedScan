"""One consultation note written by a doctor."""
from datetime import datetime


class Consultation:
    """One meeting between a doctor and a patient, and the note the doctor wrote about it."""

    def __init__(self, consultation_id, doctor_id, doctor_name, notes, date=None):
        """Keep one note. The date is now, unless a saved date is given (a note read back from the database has its
        own)."""
        self.consultation_id = consultation_id
        self.doctor_id = doctor_id
        self.doctor_name = doctor_name
        self.notes = notes
        self.date = date or datetime.now()

    def summary(self):
        """The note as one readable line: the date, the doctor's name and what they wrote."""
        return f"{self.date:%Y-%m-%d %H:%M} - Dr. {self.doctor_name}: {self.notes}"