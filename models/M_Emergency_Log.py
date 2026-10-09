from datetime import datetime


class EmergencyLog:
    """Permanent record of a doctor opening a record without consent."""

    def __init__(self, log_id, doctor_id, patient_id, reason, timestamp=None):
        self.log_id = log_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.reason = reason
        self.timestamp = timestamp or datetime.now()