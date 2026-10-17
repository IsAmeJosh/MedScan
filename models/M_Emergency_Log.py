"""The permanent record of one emergency opening."""
from datetime import datetime


class EmergencyLog:
    """The permanent record of a doctor opening a patient's record without the patient's consent. It keeps who did it,
    for which patient, the reason they gave and when, so the override can never be used unseen."""

    def __init__(self, log_id, doctor_id, patient_id, reason, timestamp=None):
        """Keep one emergency opening. The time is now unless a saved time is given."""
        self.log_id = log_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.reason = reason
        self.timestamp = timestamp or datetime.now()