"""A message for one user."""
from datetime import datetime


class Notification:
    """A message for one user, with a read or unread flag and a kind that says what it is about. Encapsulation: every
    field is private (it starts with an underscore) and is read through a property, so a page can show a message
    but can never change one by accident."""

    KINDS = ("info", "request", "approved", "denied", "revoked", "emergency", "scan", "note")
    # Where a patient is taken when they open a message of that kind. Any other kind leads to the History page.
    PATIENT_DESTINATIONS = {"request": "requests", "note": "record"}

    def __init__(self, notification_id, recipient_id, message, related_request_id=None,
                 is_read=False, timestamp=None, kind="info"):
        """Keep one message. Every field is private and is read through the properties below (encapsulation)."""
        self._notification_id = notification_id
        self._recipient_id = recipient_id
        self._message = message
        self._related_request_id = related_request_id
        self._is_read = is_read
        self._timestamp = timestamp or datetime.now()
        self._kind = kind

    @property
    def notification_id(self):
        """This message's own ID number."""
        return self._notification_id

    @property
    def recipient_id(self):
        """The ID of the user who receives this message."""
        return self._recipient_id

    @property
    def message(self):
        """The text of the message, written for the person who reads it."""
        return self._message

    @property
    def is_read(self):
        """True once the user has opened the message."""
        return self._is_read

    @property
    def timestamp(self):
        """When the message was created."""
        return self._timestamp

    @property
    def related_request_id(self):
        """The access request this message is about, or None when it is not about one."""
        return self._related_request_id

    @property
    def kind(self):
        """What the message is about: 'request', 'approved', 'denied', 'revoked', 'emergency', 'scan', 'note' or
        'info'. The pages use it to decide how to show the message and where opening it leads."""
        return self._kind

    def destination(self, role):
        """Where opening this message should lead, as a short word. A patient is sent to 'requests', 'record' or
        'history'. A doctor is always sent to 'patients', and that page then works out which patient. The pages
        turn the word into a real address."""
        if role == "Doctor":
            return "patients"
        return self.PATIENT_DESTINATIONS.get(self._kind, "history")
