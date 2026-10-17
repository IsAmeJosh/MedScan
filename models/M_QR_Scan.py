"""The record of one QR scan."""
from datetime import datetime


class QRScan:
    """One entry in the access log: a doctor scanned a patient's QR code. Scanning a live code is also the patient's
    approval, so it is logged on its own and the patient can see it in History."""

    def __init__(self, scan_id, doctor_id, patient_id, timestamp=None):
        """Keep one scan: which doctor, which patient and when."""
        self.scan_id = scan_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.timestamp = timestamp or datetime.now()
