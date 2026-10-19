"""One entry in the log of what a doctor changed in a patient's health details."""
from datetime import datetime


class HealthChange:
    """A doctor added, changed or removed an allergy, a condition, a medication or a vaccine. It is logged so the patient can see it
    in Access, History (the log is only ever added to)."""

    def __init__(self, log_id, doctor_id, patient_id, action, kind, item_name, timestamp=None):
        """Keep who did what to which item, and when."""
        self.log_id = log_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.action = action
        self.kind = kind
        self.item_name = item_name
        self.timestamp = timestamp or datetime.now()
