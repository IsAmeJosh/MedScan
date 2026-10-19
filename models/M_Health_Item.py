"""One allergy, condition, medication or vaccine in a patient's record."""
from datetime import datetime


class HealthItem(str):
    """One item of a patient's health details: an allergy, a condition, a medication or a vaccine. It IS its name (it is a str), so
    everywhere the program only wants the name (a list of allergy names, joining them with commas, comparing with a word) it simply
    works, and it also carries the details that belong to its kind: the severity and reaction of an allergy, the status and date of a
    condition, the dose, how often and start of a medication, the date a vaccine was given. Every item also remembers who added it
    and when. Inheritance: a HealthItem is a str that knows more."""

    # How each kind is written in a sentence ("Dr. Reyes added an allergy: Penicillin") and what its list is called in a MedicalRecord.
    ARTICLES = {"allergy": "an allergy", "condition": "a condition", "medication": "a medication", "vaccine": "a vaccine"}
    LISTS = {"allergy": "allergies", "condition": "conditions", "medication": "medications", "vaccine": "vaccines"}

    def __new__(cls, name, item_id=None, kind="", severity="", reaction="", status="", dose="", frequency="", date_on=None,
                added_by_role="patient", added_by_id=None, added_by_name="", added_at=None):
        """Make an item from its name and details. A detail that does not apply to the kind stays blank."""
        item = super().__new__(cls, name)
        item.item_id = item_id
        item.kind = kind
        item.severity = severity or ""
        item.reaction = reaction or ""
        item.status = status or ""
        item.dose = dose or ""
        item.frequency = frequency or ""
        item.date_on = date_on
        item.added_by_role = added_by_role
        item.added_by_id = added_by_id
        item.added_by_name = added_by_name or ""
        item.added_at = added_at or datetime.now()
        return item

    def added_by_text(self, viewer_role, viewer_id):
        """The small grey line under the item, written for whoever is looking.
        - Added by the viewer themselves, as a patient: "Added by you".
        - Added by a doctor: "Added by Dr. Maria Reyes - Oct 19, 2026" ("Added by you - ..." when the viewer is that doctor).
        - Added by the patient, and a doctor is looking: "Added by the patient"."""
        by_viewer = self.added_by_role == viewer_role.lower() and self.added_by_id == viewer_id
        if self.added_by_role == "patient":
            return "Added by you" if by_viewer else "Added by the patient"
        when = f"{self.added_at:%b} {self.added_at.day}, {self.added_at.year}"
        return f"Added by {'you' if by_viewer else 'Dr. ' + self.added_by_name} \u2013 {when}"
