class MedicalRecord:
    """The health history of one patient (allergies, surgeries, consultations)."""

    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.allergies = []
        self.surgeries = []
        self.consultations = []

    def add_allergy(self, allergy):
        if allergy and allergy not in self.allergies:
            self.allergies.append(allergy)

    def add_surgery(self, surgery):
        if surgery and surgery not in self.surgeries:
            self.surgeries.append(surgery)

    def add_consultation(self, consultation):
        # a finished session updates the overall record
        self.consultations.append(consultation)

    def latest_consultation(self):
        return self.consultations[-1] if self.consultations else None