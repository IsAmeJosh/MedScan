"""One line of a doctor's Patients list."""
from datetime import datetime


class PatientLink:
    """How one patient stands with one doctor: one line of the doctor's Patients list. Abstraction: the page only asks
    for the kind and the time. Working those out from the requests and the emergency logs is the system's job, so
    the page never needs to know how many tables were looked at. Encapsulation: its fields are private and read
    through properties, so a line cannot be changed after it is made."""

    # The order of the list, and of the filter chips above it.
    ORDER = ("access", "waiting", "emergency", "denied", "locked")
    LABELS = {"access": "Access", "waiting": "Waiting", "emergency": "Emergency", "denied": "Denied", "locked": "Locked"}

    def __init__(self, patient, kind, when=None, via="request"):
        """Keep the patient, the kind of line this is, and when it happened. The fields are private (encapsulation)."""
        self._patient = patient
        self._kind = kind
        self._when = when or datetime.now()
        self._via = via

    @property
    def patient(self):
        """The patient this line is about."""
        return self._patient

    @property
    def kind(self):
        """The kind of line: 'access' (the patient approved), 'waiting' (a request is pending), 'emergency' (opened
        through the override), 'denied' (they said no or took access back) or 'locked' (nothing has happened
        between them yet)."""
        return self._kind

    @property
    def label(self):
        """The word shown on the status pill: Access, Waiting, Emergency, Denied or Locked."""
        return self.LABELS[self._kind]

    @property
    def when(self):
        """When it happened: the approval, the request, the emergency or the denial."""
        return self._when

    @property
    def approved_by_qr(self):
        """True when the access came from the patient showing their QR code."""
        return self._kind == "access" and self._via == "qr"

    def sort_key(self):
        """The key used to sort the list: first by kind, in the order of ORDER, then newest first within each kind."""
        return (self.ORDER.index(self._kind), -self._when.timestamp())
