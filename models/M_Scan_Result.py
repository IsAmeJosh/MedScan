"""The answer to a QR scan."""
class ScanResult:
    """What happened when a doctor scanned a QR code. The page only has to look at the outcome to know what to show;
    it never needs to know how the rules decided it (abstraction).
    Encapsulation: the outcome and the patient are private and can only be read, so a result cannot be changed after
    the rules have decided it."""

    APPROVED = "approved"   # A good one-time code: the patient is approving this doctor right now.
    ALREADY = "already"     # A good one-time code, but the doctor already had access. The scan is still logged.
    FOUND = "found"         # Only the patient's ID, with no secret: it finds the patient but approves nothing.
    EXPIRED = "expired"     # The code was already used, was replaced by a newer one, or ran out of time.
    INVALID = "invalid"     # Not a MedScan patient code at all.

    def __init__(self, outcome, patient_id=None):
        """Keep the outcome and the patient it names. Both are private and read-only (encapsulation)."""
        self._outcome = outcome
        self._patient_id = patient_id

    @property
    def outcome(self):
        """One of the outcome words listed above: APPROVED, ALREADY, FOUND, EXPIRED or INVALID."""
        return self._outcome

    @property
    def patient_id(self):
        """The patient the code names, or None when it is not a MedScan code."""
        return self._patient_id

    @property
    def opens_record(self):
        """True when the doctor can now open the record: either the scan approved them, or they already had access."""
        return self._outcome in (self.APPROVED, self.ALREADY)
