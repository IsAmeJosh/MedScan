"""The one-time part of a patient's QR code."""
import secrets


class QRToken:
    """A secret that is put inside a patient's QR code. Showing the code to a doctor in person is the patient's
    approval, so the secret works once and only for a few minutes: a doctor who only knows the patient's ID cannot
    approve themselves. Encapsulation: the secret and its age are private and can only be read. How much time is
    left is worked out from the age the database measured (not from this computer's clock), so the two clocks can
    never disagree."""

    LIFETIME_SECONDS = 300      # A code stops working five minutes after it was made.

    def __init__(self, token_id, patient_id, value, age_seconds):
        """Keep the secret and its age. Both are private (encapsulation)."""
        self._token_id = token_id
        self._patient_id = patient_id
        self.__value = value
        self._age_seconds = max(0, int(age_seconds))

    @staticmethod
    def make_value():
        """Make a new random secret: 32 hex characters (128 bits), far too many to guess."""
        return secrets.token_hex(16)

    @property
    def token_id(self):
        """This token's own ID number."""
        return self._token_id

    @property
    def patient_id(self):
        """The patient this code belongs to."""
        return self._patient_id

    @property
    def value(self):
        """The secret text that goes inside the QR code."""
        return self.__value

    @property
    def seconds_left(self):
        """How many whole seconds are left before the code stops working. It is 0 once the time has run out."""
        return max(0, self.LIFETIME_SECONDS - self._age_seconds)
