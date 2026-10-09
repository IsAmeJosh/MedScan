class AccessRequest:
    """A doctor's request to view a patient's record; the patient decides."""

    def __init__(self, request_id, doctor_id, patient_id, status="Pending"):
        self.request_id = request_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.status = status

    def approve(self):
        """Patient allows the doctor."""
        self.status = "Approved"

    def deny(self):
        """Patient refuses the doctor."""
        self.status = "Denied"

    def revoke(self):
        """Patient takes back access they had approved."""
        self.status = "Revoked"

    def is_approved(self):
        """True while the patient's approval is in force."""
        return self.status == "Approved"
