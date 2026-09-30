class AccessRequest:
    """A doctor's request to view a patient's record; the patient decides."""

    def __init__(self, request_id, doctor_id, patient_id):
        self.request_id = request_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.status = "Pending"

    def approve(self):
        self.status = "Approved"

    def deny(self):
        self.status = "Denied"

    def is_approved(self):
        return self.status == "Approved"