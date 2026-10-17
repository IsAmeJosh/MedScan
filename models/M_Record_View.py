"""The record of one opening of a patient's record."""
from datetime import datetime


class RecordView:
    """One entry in the access log: a doctor opened a patient's record, either because the patient had approved them
    or through emergency access."""

    def __init__(self, view_id, doctor_id, patient_id, via, timestamp=None):
        """Keep one opening: which doctor, which patient, how they were allowed in ('approved' or 'emergency') and
        when."""
        self.view_id = view_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.via = via  # "approved" (the patient said yes) or "emergency" (the override).
        self.timestamp = timestamp or datetime.now()
