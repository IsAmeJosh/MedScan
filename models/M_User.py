"""The base class of every account, with the fields and behaviour that patients and doctors share."""
from datetime import datetime


class User:
    """The base class of everyone who logs in to MedScan, patient or doctor. It holds what every account has in common
    (ID, name, password, role) so that Patient and Doctor only have to add what makes them different (inheritance).
    Encapsulation: the fields start with an underscore and are read through the properties below, and the password
    is name-mangled (__password), which keeps it out of reach of the rest of the program. The only way to use it is
    login()."""

    ID_PREFIX = "US"  # Subclasses replace this with their own prefix (polymorphism): Patient uses PT and Doctor uses DR.

    def __init__(self, user_id, name, password, role, created_year=None, password_changed_at=None):
        """Set up the fields every account shares. The password goes into a private attribute and never leaves this
        class. When no year is given the account counts as made this year, and the password as set today."""
        self._user_id = user_id
        self._name = name
        self.__password = password  # Private (name-mangled): it is only ever compared inside login().
        self._role = role
        self._created_year = created_year or datetime.now().year
        self._password_changed_at = password_changed_at or datetime.now()

    @property
    def password_changed_at(self):
        """When the password was last set. For a new account this is the day it was made, until the password is
        changed."""
        return self._password_changed_at

    @property
    def created_on(self):
        """The day the account was made, for the ID page. Passwords cannot be changed yet, so the day the password
        was set is the day the account was made."""
        return self._password_changed_at.date()

    @property
    def user_id(self):
        """The account's ID number. It is read-only on purpose (encapsulation): there is a getter but no setter, so an
        ID can never be changed once the account exists."""
        return self._user_id

    @property
    def name(self):
        """The name shown on screen. Read-only, like the ID."""
        return self._name

    @property
    def role(self):
        """Either 'Patient' or 'Doctor'. The pages use it to decide which menu and which screens a person gets."""
        return self._role

    @property
    def display_id(self):
        """The ID the way people read it, such as PT-2026-01001: the account type (PT or DR), the year the account was
        made, and the ID number padded to five digits. Only the last part is the real ID the database uses."""
        return f"{self.ID_PREFIX}-{self._created_year}-{self._user_id:05d}"

    @property
    def created_year(self):
        """The year the account was made. It is the middle part of the display ID."""
        return self._created_year

    def login(self, user_id, password):
        """Check an ID and a password together. It returns True only when both match. The comparison happens here,
        inside the class that owns the password, so no other part of the program ever has to read it."""
        return self._user_id == user_id and self.__password == password

    def __str__(self):
        """A short description that is handy when printing or debugging, such as 'Patient #1001: Juan Dela Cruz'."""
        return f"{self._role} #{self._user_id}: {self._name}"
