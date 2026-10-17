"""A doctor's request for access to one patient's record."""
from datetime import datetime


class AccessRequest:
    """A doctor's request to see one patient's record. The patient decides: they can approve it, deny it, and later
    take an approval back. A request can also be approved on the spot when the patient shows their one-time QR code
    in person (via = "qr")."""

    def __init__(self, request_id, doctor_id, patient_id, status="Pending", created_at=None, decided_at=None,
                 via="request"):
        """Create a request. By default it starts as Pending, the time of asking is now, and nobody has answered yet,
        so the answer date and the way it was answered fill in later."""
        self.request_id = request_id
        self.doctor_id = doctor_id
        self.patient_id = patient_id
        self.status = status
        self.created_at = created_at or datetime.now()   # When the doctor asked.
        self.decided_at = decided_at                      # None until the patient answers.
        self.via = via                                    # "request" (answered) or "qr" (they showed their code).

    def approve(self, via="request"):
        """The patient says yes, either by answering the request or by showing their one-time QR code (via='qr'). The
        time and the way are recorded."""
        self.status = "Approved"
        self.via = via
        self.decided_at = datetime.now()

    def deny(self):
        """The patient says no. The doctor is free to ask again later."""
        self.status = "Denied"
        self.decided_at = datetime.now()

    def revoke(self):
        """The patient takes back an approval they gave earlier, so the doctor loses access right away."""
        self.status = "Revoked"
        self.decided_at = datetime.now()

    def is_approved(self):
        """True while the patient's approval is still in force: it was approved and has not been taken back."""
        return self.status == "Approved"

    @property
    def approved_by_qr(self):
        """True when the doctor got in because the patient showed their QR code and not because they answered a
        request. The History page shows this difference."""
        return self.via == "qr" and self.status == "Approved"
