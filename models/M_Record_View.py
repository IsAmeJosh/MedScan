from datetime import datetime


class RecordView:
    """One log entry: a doctor opened a patient's record."""

    def __init__(self, view_id, doctor_id, patient_id, via, timestamp=None):
        self.view_id = view_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.via = via  # "approved" (patient said yes) or "emergency" (override)
        self.timestamp = timestamp or datetime.now()
