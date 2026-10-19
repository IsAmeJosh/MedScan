"""The edit sheets for a person's own details (Profile and My Record) and for the health items (allergies, conditions, medications,
vaccines). One template (G_Edit_Sheet.html) serves every sheet: this file says which fields each sheet has, with what labels, in
what order, and works out what each box should start with."""
from django.urls import reverse

from gui.G_Filters import mobile
from logic.L_MedScan_System import MedScanSystem
from models.M_Health_Item import HealthItem
from models.M_Medical_Record import BLOOD_TYPES

# What each field looks like in a sheet: its label, the kind of box, and the small hints.
FIELDS = {
    "date_of_birth": {"label": "Date of birth", "kind": "text", "inputmode": "numeric", "placeholder": "MM/DD/YYYY", "format": "date"},
    "sex": {"label": "Sex", "kind": "select", "choices": [("Male", "Male"), ("Female", "Female")]},
    "blood_type": {"label": "Blood type", "kind": "select", "choices": [(b, b or "Not set") for b in BLOOD_TYPES]},
    "height_cm": {"label": "Height", "kind": "text", "inputmode": "numeric", "placeholder": "cm"},
    "weight_kg": {"label": "Weight", "kind": "text", "inputmode": "decimal", "placeholder": "kg"},
    "contact_number": {"label": "Mobile", "kind": "text", "inputmode": "tel", "placeholder": "0917 123 4567", "format": "mobile"},
    "emergency_name": {"label": "Name", "kind": "text", "inputmode": "text", "placeholder": ""},
    "emergency_relationship": {"label": "Relationship", "kind": "text", "inputmode": "text", "placeholder": ""},
    "emergency_mobile": {"label": "Mobile", "kind": "text", "inputmode": "tel", "placeholder": "0917 123 4567", "format": "mobile"},
    "surgeries": {"label": "Past surgeries", "kind": "chips"},
}

# The sheets: each is named after the panel it opens from, and lists only that panel's fields.
PATIENT_SHEETS = {
    "basic": ("Basic info", ("date_of_birth", "sex", "blood_type", "height_cm", "weight_kg")),
    "contact": ("Contact", ("contact_number",)),
    "emergency": ("Emergency contact", ("emergency_name", "emergency_relationship", "emergency_mobile")),
    "personal": ("Personal details", ("date_of_birth", "sex", "blood_type", "contact_number")),
    "surgeries": ("Past surgeries", ("surgeries",)),
}
DOCTOR_SHEETS = {"work": ("Work details", ("contact_number",))}

DATE_BOX = {"kind": "text", "inputmode": "numeric", "placeholder": "MM/DD/YYYY", "format": "date"}
SEVERITY_CHOICES = [(s, s) for s in MedScanSystem.SEVERITIES]
STATUS_CHOICES = [(s, s) for s in MedScanSystem.STATUSES]
# The health item sheets: the title and the boxes of each kind (the field names are the ones MedScanSystem.HEALTH_FIELDS lists).
HEALTH_SHEETS = {
    "allergy": ("Allergy", [("name", dict(label="Allergen", kind="text", inputmode="text", placeholder="")),
                            ("severity", dict(label="Severity", kind="select", choices=SEVERITY_CHOICES, default="Mild")),
                            ("reaction", dict(label="Reaction (optional)", kind="text", inputmode="text", placeholder=""))]),
    "condition": ("Condition", [("name", dict(label="Name", kind="text", inputmode="text", placeholder="")),
                                ("status", dict(label="Status", kind="select", choices=STATUS_CHOICES, default="Active")),
                                ("date_on", dict(label="Diagnosed (optional)", **DATE_BOX))]),
    "medication": ("Medication", [("name", dict(label="Name", kind="text", inputmode="text", placeholder="")),
                                  ("dose", dict(label="Dose", kind="text", inputmode="text", placeholder="e.g. 500 mg")),
                                  ("frequency", dict(label="How often", kind="text", inputmode="text", placeholder="e.g. twice daily")),
                                  ("date_on", dict(label="Started (optional)", **DATE_BOX))]),
    "vaccine": ("Vaccine", [("name", dict(label="Name", kind="text", inputmode="text", placeholder="")),
                            ("date_on", dict(label="Given on", **DATE_BOX))]),
}
HEALTH_KINDS = tuple(HEALTH_SHEETS)


def sheets_for(role):
    """The sheets a person with this role may open: {name: (title, fields)}."""
    return DOCTOR_SHEETS if role == "Doctor" else PATIENT_SHEETS


def start_value(user, field):
    """The text a box starts with: what the person has saved, written the way the forms write it."""
    if field == "blood_type":
        return user.record.blood_type
    value = getattr(user, field, None)
    if field == "date_of_birth":
        return value.strftime("%m/%d/%Y") if value else ""
    if field in ("contact_number", "emergency_mobile"):
        return mobile(value) or ""
    if field == "surgeries":
        return ", ".join(user.record.surgeries)
    if field == "weight_kg":
        return "" if value is None else f"{value:f}".rstrip("0").rstrip(".")
    return "" if value is None else str(value)


def _row(field, spec, value, error):
    """One box of a sheet, as the template draws it."""
    row = dict(spec, name=field, value=value, error=error)
    if row["kind"] == "select":
        row["choices"] = [{"value": v, "label": label} for v, label in row["choices"]]
    return row


def build_sheets(user, names, flash=None):
    """The sheets to put on one page, as {name: sheet} for the template. After a failed save, flash holds what the person
    typed and the messages for that sheet ({"sheet", "values", "errors"}), so the sheet opens again with both."""
    titles = sheets_for(user.role)
    built = {}
    for name in names:
        title, fields = titles[name]
        again = flash if flash and flash.get("sheet") == name else {}
        rows = [_row(field, FIELDS[field], again.get("values", {}).get(field, start_value(user, field)),
                     again.get("errors", {}).get(field, "")) for field in fields]
        built[name] = {"name": name, "id": f"edit-{name}", "title": title, "fields": rows, "action": reverse("edit_details", args=[name]),
                       "item_id": "", "remove_url": "", "item_name": ""}
    return built


def _item_value(item, field):
    """The text a health item's box starts with."""
    if field == "name":
        return str(item)
    value = getattr(item, field)
    return value.strftime("%m/%d/%Y") if field == "date_on" and value else ("" if value is None else str(value))


def build_health_sheets(patient, viewer, flash=None, kinds=HEALTH_KINDS, only_new=False):
    """The sheets for the health items of one patient, as a list for the page: for every kind first the sheet that adds a new item
    (id edit-allergy-new) and then one pre-filled sheet for each item already there (id edit-allergy-12), unless only_new. The
    sheets post to the patient's own address when the patient is looking, and to the doctor's address when a doctor is, and an
    item's sheet has a Remove button. After a failed save, flash holds what was typed and the messages for that sheet."""
    doctor = viewer.role == "Doctor"
    sheets = []
    for kind in kinds:
        title, fields = HEALTH_SHEETS[kind]
        items = getattr(patient.record, HealthItem.LISTS[kind])
        for item in ([None] if only_new else [None, *items]):
            name = f"{kind}-{item.item_id if item else 'new'}"
            again = flash if flash and flash.get("sheet") == name else {}
            rows = []
            for field, spec in fields:
                start = _item_value(item, field) if item else spec.get("default", "")
                rows.append(_row(field, spec, again.get("values", {}).get(field, start), again.get("errors", {}).get(field, "")))
            save_url = reverse("doctor_save_health", args=[patient.user_id, kind]) if doctor else reverse("save_health", args=[kind])
            remove_url = ""
            if item:
                remove_url = (reverse("doctor_remove_health", args=[patient.user_id, item.item_id]) if doctor
                              else reverse("remove_health", args=[item.item_id]))
            sheets.append({"name": name, "id": f"edit-{name}", "title": title, "fields": rows, "action": save_url,
                           "item_id": item.item_id if item else "", "remove_url": remove_url, "item_name": str(item) if item else ""})
    return sheets
