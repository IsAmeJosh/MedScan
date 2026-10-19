"""A patient's health history: allergies, conditions, medications, vaccines, surgeries, blood type and consultation notes."""
from models.M_Health_Item import HealthItem
BLOOD_TYPES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]  # "" means the blood type has not been set yet.


class MedicalRecord:
    """The health history of one patient: allergies, conditions, medications and vaccines (each a HealthItem that knows who added
    it and when), past surgeries (plain names), blood type and the consultation notes doctors have written. It is plain data with
    a few helpers that keep the lists tidy."""

    def __init__(self, patient_id):
        """Start an empty record for one patient. Every list begins empty and the blood type begins as not set."""
        self.patient_id = patient_id
        self.allergies = []
        self.conditions = []
        self.medications = []
        self.vaccines = []
        self.surgeries = []
        self.blood_type = ""
        self.consultations = []

    def add_allergy(self, allergy):
        """Add an allergy to the list, unless it is blank or already there. Skipping blanks and repeats keeps the list
        clean however the text was typed."""
        if allergy and allergy not in self.allergies:
            self.allergies.append(allergy)

    def add_condition(self, condition):
        """Add a condition to the list, unless it is blank or already there."""
        if condition and condition not in self.conditions:
            self.conditions.append(condition)

    def add_vaccine(self, vaccine):
        """Add a vaccine to the list. The same vaccine can be given more than once (a booster), so only a blank is skipped."""
        if vaccine:
            self.vaccines.append(vaccine)

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
            self.add_allergy(HealthItem(a.strip(), kind="allergy") if a.strip() else "")
        for s in surgeries.split(","):
            self.add_surgery(s.strip())
        for m in medications.split(","):
            self.add_medication(HealthItem(m.strip(), kind="medication") if m.strip() else "")
        self.blood_type = blood_type

    def replace_surgeries(self, text):
        """Replace the list of past surgeries from comma-separated text, and leave everything else as it is. Blanks and repeats
        are dropped."""
        self.surgeries = []
        for item in text.split(","):
            self.add_surgery(item.strip())

    def latest_vaccine(self):
        """The vaccine most recently given (the one with the newest date; one with no date counts as oldest), or None."""
        dated = [v for v in self.vaccines if v.date_on]
        return max(dated, key=lambda v: (v.date_on, v.item_id or 0)) if dated else (self.vaccines[-1] if self.vaccines else None)

    def add_consultation(self, consultation):
        """Attach a consultation note to this record. Notes are added in the order they were written, so the newest is
        last."""
        self.consultations.append(consultation)
