class User:
    """Base class for everyone who logs in to MedScan."""

    def __init__(self, user_id, name, password, role):
        self._user_id = user_id
        self._name = name
        self.__password = password  # private: only checked through login()
        self._role = role

    @property
    def user_id(self):
        return self._user_id

    @property
    def name(self):
        return self._name

    @property
    def role(self):
        return self._role

    def login(self, user_id, password):
        return self._user_id == user_id and self.__password == password

    def __str__(self):
        return f"{self._role} #{self._user_id}: {self._name}"