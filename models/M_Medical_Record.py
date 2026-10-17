"""A patient's health history: allergies, surgeries, medications, blood type and consultation notes."""
BLOOD_TYPES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]  # "" means the blood type has not been set yet.


class MedicalRecord:
    """The health history of one patient: allergies, surgeries, medications, blood type and the consultation notes
    doctors have written. It is plain data with a few helpers that keep the lists tidy."""

    def __init__(self, patient_id):
        """Start an empty record for one patient. Every list begins empty and the blood type begins as not set."""
        self.patient_id = patient_id
        self.allergies = []
        self.surgeries = []
        self.medications = []
        self.blood_type = ""
        self.consultations = []

    def add_allergy(self, allergy):
        """Add an allergy to the list, unless it is blank or already there. Skipping blanks and repeats keeps the list
        clean however the text was typed."""
        if allergy and allergy not in self.allergies:
            self.allergies.append(allergy)

    def add_surgery(self, surgery):
        """Add a past surgery to the list, unless it is blank or already there."""
        if surgery and surgery not in self.surgeries:
            self.surgeries.append(surgery)

    def add_medication(self, medication):
        """Add a medication to the list, unless it is blank or already there."""
        if medication and medication not in self.medications:
            self.medications.append(medication)

    def replace_history(self, allergies="", surgeries="", medications="", blood_type=""):
        """Throw away the current history and rebuild it from comma-separated text, for example allergies='Penicillin,
        Peanuts'. Each piece is trimmed, and the add_ methods drop blanks and repeats."""
        self.allergies, self.surgeries, self.medications = [], [], []
        for a in allergies.split(","):
            self.add_allergy(a.strip())
        for s in surgeries.split(","):
            self.add_surgery(s.strip())
        for m in medications.split(","):
            self.add_medication(m.strip())
        self.blood_type = blood_type

    def add_consultation(self, consultation):
        """Attach a consultation note to this record. Notes are added in the order they were written, so the newest is
        last."""
        self.consultations.append(consultation)
