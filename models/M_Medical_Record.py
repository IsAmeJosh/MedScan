BLOOD_TYPES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]  # "" = not set


class MedicalRecord:
    """The health history of one patient (allergies, surgeries, medications, consultations)."""

    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.allergies = []
        self.surgeries = []
        self.medications = []
        self.blood_type = ""
        self.consultations = []

    def add_allergy(self, allergy):
        """Add an allergy unless it is blank or already listed."""
        if allergy and allergy not in self.allergies:
            self.allergies.append(allergy)

    def add_surgery(self, surgery):
        """Add a surgery unless it is blank or already listed."""
        if surgery and surgery not in self.surgeries:
            self.surgeries.append(surgery)

    def add_medication(self, medication):
        """Add a medication unless it is blank or already listed."""
        if medication and medication not in self.medications:
            self.medications.append(medication)

    def replace_history(self, allergies="", surgeries="", medications="", blood_type=""):
        """Start the history over from comma-separated text."""
        self.allergies, self.surgeries, self.medications = [], [], []
        for a in allergies.split(","):
            self.add_allergy(a.strip())
        for s in surgeries.split(","):
            self.add_surgery(s.strip())
        for m in medications.split(","):
            self.add_medication(m.strip())
        self.blood_type = blood_type

    def add_consultation(self, consultation):
        """Attach a finished consultation to this record."""
        # a finished session updates the overall record
        self.consultations.append(consultation)

    def latest_consultation(self):
        """The newest consultation, or None if there are none."""
        return self.consultations[-1] if self.consultations else None
