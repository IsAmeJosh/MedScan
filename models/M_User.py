from datetime import datetime


class User:
    """Base class for everyone who logs in to MedScan."""

    ID_PREFIX = "US"  # subclasses replace this with their own prefix (polymorphism)

    def __init__(self, user_id, name, password, role, created_year=None):
        self._user_id = user_id
        self._name = name
        self.__password = password  # private: only checked through login()
        self._role = role
        self._created_year = created_year or datetime.now().year

    @property
    def user_id(self):
        """Read-only ID number (encapsulation: no setter)."""
        return self._user_id

    @property
    def name(self):
        """Read-only display name."""
        return self._name

    @property
    def role(self):
        """'Patient' or 'Doctor'."""
        return self._role

    @property
    def display_id(self):
        """Readable ID such as PT-2026-01001. The number inside is the real ID."""
        return f"{self.ID_PREFIX}-{self._created_year}-{self._user_id:05d}"

    @property
    def created_year(self):
        """The year the account was created (part of the display ID)."""
        return self._created_year

    def credential_for_storage(self):
        """The password, for the store only. Plain text for now (hashing is a later step)."""
        return self.__password

    def login(self, user_id, password):
        """Check an ID and password. The password stays private inside this class."""
        return self._user_id == user_id and self.__password == password

    def __str__(self):
        return f"{self._role} #{self._user_id}: {self._name}"
