"""The health details: allergies, conditions, medications and vaccines. A patient adds, changes and removes them on their own record; a
doctor can do the same only while the record is open to them (a locked record answers 403); every item says who added it; a
doctor's change is announced to the patient and logged; and an empty list reads "Not added" with an Add link."""
import re
import unittest
from datetime import date, timedelta

from django.test import Client

from tests.helpers import BORN, PASSWORD, add_health_samples, approve, count, fresh_system, html, login, new_patient, rows

MEDICAL = "/record/?tab=medical"
TOMORROW = (date.today() + timedelta(days=1)).strftime("%m/%d/%Y")

GIVEN = {
    "allergy": {"name": "Latex", "severity": "Moderate", "reaction": "Rash"},
    "condition": {"name": "Asthma", "status": "Active", "date_on": "02/11/2019"},
    "medication": {"name": "Metformin", "dose": "500 mg", "frequency": "twice daily", "date_on": "01/05/2025"},
    "vaccine": {"name": "Hepatitis B", "date_on": "03/02/2024"},
}
CHANGED = {
    "allergy": {"name": "Latex", "severity": "Severe", "reaction": "Hives"},
    "condition": {"name": "Asthma", "status": "Managed", "date_on": "02/11/2019"},
    "medication": {"name": "Metformin", "dose": "1000 mg", "frequency": "once daily", "date_on": "01/05/2025"},
    "vaccine": {"name": "Hepatitis B", "date_on": "03/03/2024"},
}
LISTS = {"allergy": "allergies", "condition": "conditions", "medication": "medications", "vaccine": "vaccines"}


class HealthTestCase(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def items(self, kind, patient_id=1001):
        return getattr(self.s.get_patient(patient_id).record, LISTS[kind])

    def item(self, kind, name, patient_id=1001):
        return next(i for i in self.items(kind, patient_id) if str(i) == name)


class PatientEditsOwnRecord(HealthTestCase):
    def test_a_patient_adds_changes_and_removes_every_kind(self):
        for kind in GIVEN:
            before = len(self.items(kind))
            r = self.pat.post(f"/health/{kind}/", {**GIVEN[kind], "next": MEDICAL}, follow=True)
            self.assertIn("<span>Saved</span>", html(r), kind)
            self.assertEqual(len(self.items(kind)), before + 1, kind)
            item = self.item(kind, GIVEN[kind]["name"])
            self.assertEqual((item.added_by_role, item.added_by_id), ("patient", 1001))
            r = self.pat.post(f"/health/{kind}/", {**CHANGED[kind], "item_id": item.item_id, "next": MEDICAL}, follow=True)
            self.assertIn("<span>Saved</span>", html(r), kind)
            self.assertEqual(len(self.items(kind)), before + 1, kind)              # changed, not added again
            changed = self.item(kind, CHANGED[kind]["name"])
            self.assertEqual(changed.item_id, item.item_id)
            self.assertEqual((changed.added_by_role, changed.added_at), (item.added_by_role, item.added_at))   # who and when stay
            self.pat.post(f"/health/{item.item_id}/remove/", {"next": MEDICAL})
            self.assertEqual(len(self.items(kind)), before, kind)

    def test_the_saved_details_are_what_was_typed(self):
        self.pat.post("/health/allergy/", {**GIVEN["allergy"], "next": MEDICAL})
        allergy = self.item("allergy", "Latex")
        self.assertEqual((allergy.severity, allergy.reaction), ("Moderate", "Rash"))
        self.pat.post("/health/medication/", {**GIVEN["medication"], "next": MEDICAL})
        medication = self.item("medication", "Metformin")
        self.assertEqual((medication.dose, medication.frequency, medication.date_on), ("500 mg", "twice daily", date(2025, 1, 5)))
        self.pat.post("/health/vaccine/", {**GIVEN["vaccine"], "next": MEDICAL})
        self.assertEqual(self.item("vaccine", "Hepatitis B").date_on, date(2024, 3, 2))

    def test_a_patient_cannot_change_or_remove_another_patients_item(self):
        other = new_patient(self.s, "Other Patient", PASSWORD, "Female", BORN)
        self.s.save_health_item(other, other.user_id, "allergy", GIVEN["allergy"])
        theirs = self.item("allergy", "Latex", other.user_id)
        r = self.pat.post(f"/health/{theirs.item_id}/remove/", {"next": MEDICAL})
        self.assertEqual(r.status_code, 404)
        r = self.pat.post("/health/allergy/", {**CHANGED["allergy"], "item_id": theirs.item_id, "next": MEDICAL})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.item("allergy", "Latex", other.user_id).severity, "Moderate")
        self.assertEqual(self.pat.post(f"/patient/{other.user_id}/health/allergy/", GIVEN["allergy"]).status_code, 403)   # a patient has no doctor address

    def test_someone_who_is_not_logged_in_is_sent_to_the_login_page(self):
        self.assertEqual(Client().post("/health/allergy/", GIVEN["allergy"])["Location"], "/")

    def test_an_address_opened_by_hand_changes_nothing(self):
        before = len(self.items("allergy"))
        self.pat.get("/health/allergy/")
        self.assertEqual(len(self.items("allergy")), before)

    def test_the_patient_themselves_is_not_notified_or_logged(self):
        self.pat.post("/health/allergy/", {**GIVEN["allergy"], "next": MEDICAL})
        self.assertEqual(count("tb_health_log"), 0)
        self.assertEqual([n for n in self.s.inbox(1001) if "added an allergy" in n.message], [])


class Checks(HealthTestCase):
    def refused(self, kind, fields, field, message, sheet="new"):
        r = self.pat.post(f"/health/{kind}/", {**fields, "next": MEDICAL})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith(f"sheet=edit-{kind}-{sheet}"), r["Location"])
        page = html(self.pat.get(r["Location"]))
        box = re.search(rf'<dialog id="edit-{kind}-{sheet}".*?</dialog>', page, re.S).group(0)
        found = re.search(rf'<label for="edit-{kind}-{sheet}-{field}">.*?<p class="field-error" role="alert">([^<]+)</p>', box, re.S)
        self.assertIsNotNone(found, message)
        self.assertEqual(found.group(1), message)

    def test_every_kind_needs_a_name(self):
        self.refused("allergy", {**GIVEN["allergy"], "name": " "}, "name", "Enter the allergen.")
        self.refused("condition", {**GIVEN["condition"], "name": ""}, "name", "Enter the name of the condition.")
        self.refused("medication", {**GIVEN["medication"], "name": ""}, "name", "Enter the name of the medication.")
        self.refused("vaccine", {**GIVEN["vaccine"], "name": ""}, "name", "Enter the name of the vaccine.")

    def test_severity_and_status_come_from_the_lists(self):
        self.refused("allergy", {**GIVEN["allergy"], "severity": "Deadly"}, "severity", "Choose Mild, Moderate or Severe.")
        self.refused("condition", {**GIVEN["condition"], "status": "Gone"}, "status", "Choose Active, Managed or Resolved.")

    def test_a_vaccine_needs_a_date_that_is_not_in_the_future(self):
        self.refused("vaccine", {**GIVEN["vaccine"], "date_on": ""}, "date_on", "Enter the date it was given, like 09/14/2026.")
        self.refused("vaccine", {**GIVEN["vaccine"], "date_on": TOMORROW}, "date_on", "The date cannot be in the future.")
        self.refused("vaccine", {**GIVEN["vaccine"], "date_on": "13/45/2000"}, "date_on", "Enter a date like 04/04/2026 (month/day/year).")

    def test_the_other_dates_are_optional_but_never_in_the_future(self):
        self.pat.post("/health/condition/", {**GIVEN["condition"], "date_on": "", "next": MEDICAL})
        self.assertIsNone(self.item("condition", "Asthma").date_on)
        self.refused("medication", {**GIVEN["medication"], "date_on": TOMORROW}, "date_on", "The date cannot be in the future.")

    def test_nothing_is_saved_when_a_box_is_wrong_and_what_was_typed_stays(self):
        before = len(self.items("allergy"))
        self.refused("allergy", {"name": "Dust", "severity": "Deadly", "reaction": "Cough"}, "severity", "Choose Mild, Moderate or Severe.")
        self.assertEqual(len(self.items("allergy")), before)
        page = html(self.pat.get("/record/?tab=medical&sheet=edit-allergy-new"))
        self.assertNotIn("field-error", page)                                              # shown once only

    def test_a_wrong_edit_opens_that_items_own_sheet(self):
        item = self.item("allergy", "Penicillin")
        r = self.pat.post("/health/allergy/", {"name": "", "severity": "Severe", "item_id": item.item_id, "next": MEDICAL})
        self.assertTrue(r["Location"].endswith(f"sheet=edit-allergy-{item.item_id}"), r["Location"])
        self.assertEqual(str(self.item("allergy", "Penicillin")), "Penicillin")

    def test_a_name_that_is_too_long_is_refused(self):
        self.refused("allergy", {**GIVEN["allergy"], "name": "A" * 201}, "name", "Allergen is too long (at most 200 characters).")


class DoctorEditsOnlyWhileTheRecordIsOpen(HealthTestCase):
    def test_a_doctor_with_open_access_adds_changes_and_removes(self):
        approve(self.s)
        for kind in GIVEN:
            r = self.doc.post(f"/patient/1001/health/{kind}/", {**GIVEN[kind], "next": "/patient/1001/?tab=medical"}, follow=True)
            self.assertEqual(r.status_code, 200)
            item = self.item(kind, GIVEN[kind]["name"])
            self.assertEqual((item.added_by_role, item.added_by_id, item.added_by_name), ("doctor", 2001, "Reyes"), kind)
            self.doc.post(f"/patient/1001/health/{kind}/", {**CHANGED[kind], "item_id": item.item_id})
            self.assertEqual(str(self.item(kind, CHANGED[kind]["name"])), CHANGED[kind]["name"])
            self.doc.post(f"/patient/1001/health/{item.item_id}/remove/", {})
            self.assertNotIn(item.item_id, [i.item_id for i in self.items(kind)], kind)

    def test_a_doctor_whose_record_is_locked_gets_403_and_nothing_changes(self):
        before = {kind: len(self.items(kind)) for kind in GIVEN}
        for kind in GIVEN:
            self.assertEqual(self.doc.post(f"/patient/1001/health/{kind}/", GIVEN[kind]).status_code, 403, kind)
        penicillin = self.item("allergy", "Penicillin")
        self.assertEqual(self.doc.post(f"/patient/1001/health/{penicillin.item_id}/remove/", {}).status_code, 403)
        self.assertEqual(self.doc.post("/health/allergy/", GIVEN["allergy"]).status_code, 403)       # and not through the patient's address
        self.assertEqual({kind: len(self.items(kind)) for kind in GIVEN}, before)
        self.assertEqual(count("tb_health_log"), 0)

    def test_the_lock_comes_back_when_the_patient_takes_the_access_away(self):
        request = approve(self.s)
        self.assertEqual(self.doc.post("/patient/1001/health/allergy/", GIVEN["allergy"]).status_code, 302)
        self.s.revoke_access(request.request_id, 1001)
        self.assertEqual(self.doc.post("/patient/1001/health/vaccine/", GIVEN["vaccine"]).status_code, 403)

    def test_an_emergency_opening_lets_the_doctor_edit_while_it_lasts(self):
        self.s.emergency_access(self.s.get_doctor(2001), 1001, "Collapsed")
        self.assertEqual(self.doc.post("/patient/1001/health/allergy/", GIVEN["allergy"]).status_code, 302)
        self.assertEqual(str(self.item("allergy", "Latex")), "Latex")

    def test_a_doctor_cannot_use_the_patient_addresses_and_an_unknown_patient_is_404(self):
        approve(self.s)
        self.assertEqual(self.doc.post("/health/allergy/", GIVEN["allergy"]).status_code, 403)
        self.assertEqual(self.doc.post("/patient/9999/health/allergy/", GIVEN["allergy"]).status_code, 404)

    def test_the_item_must_belong_to_the_patient_in_the_address(self):
        approve(self.s)
        other = new_patient(self.s, "Other Patient", PASSWORD, "Female", BORN)
        self.s.save_health_item(other, other.user_id, "allergy", GIVEN["allergy"])
        theirs = self.item("allergy", "Latex", other.user_id)
        self.assertEqual(self.doc.post(f"/patient/1001/health/{theirs.item_id}/remove/", {}).status_code, 404)
        self.assertEqual(self.item("allergy", "Latex", other.user_id).item_id, theirs.item_id)


class ThePatientHearsAboutADoctorsChange(HealthTestCase):
    def test_a_notification_and_an_access_history_line_for_every_change(self):
        approve(self.s)
        self.doc.post("/patient/1001/health/allergy/", {"name": "Aspirin", "severity": "Mild", "reaction": ""})
        item = self.item("allergy", "Aspirin")
        self.doc.post("/patient/1001/health/allergy/", {"name": "Aspirin", "severity": "Severe", "reaction": "", "item_id": item.item_id})
        self.doc.post(f"/patient/1001/health/{item.item_id}/remove/", {})
        self.doc.post("/patient/1001/health/vaccine/", GIVEN["vaccine"])
        messages = [n.message for n in self.s.inbox(1001)]
        for text in ("Dr. Reyes added an allergy: Aspirin", "Dr. Reyes changed an allergy: Aspirin",
                     "Dr. Reyes removed an allergy: Aspirin", "Dr. Reyes added a vaccine: Hepatitis B"):
            self.assertIn(text, messages)
        self.assertEqual(count("tb_health_log", "patient_id = 1001"), 4)
        history = html(self.pat.get("/access/?tab=history"))
        for text in ("added an allergy: Aspirin", "removed an allergy: Aspirin", "added a vaccine: Hepatitis B"):
            self.assertIn(text, history)

    def test_a_failed_save_tells_nobody(self):
        approve(self.s)
        before = len(self.s.inbox(1001))
        self.doc.post("/patient/1001/health/vaccine/", {"name": "Tdap", "date_on": TOMORROW})
        self.assertEqual(len(self.s.inbox(1001)), before)
        self.assertEqual(count("tb_health_log"), 0)


class WhoAddedIt(HealthTestCase):
    def test_the_grey_line_names_the_person_for_whoever_is_looking(self):
        approve(self.s)
        today = date.today()
        written = f"{today:%b} {today.day}, {today.year}"
        self.doc.post("/patient/1001/health/allergy/", {"name": "Aspirin", "severity": "Mild", "reaction": ""})
        mine = html(self.pat.get(MEDICAL))
        self.assertIn(f"Added by Dr. Reyes – {written}", mine)                   # the patient sees the doctor
        self.assertIn("Added by you", mine)                                                  # and their own Penicillin
        seen = html(self.doc.get("/patient/1001/?tab=medical"))
        self.assertIn(f"Added by you – {written}", seen)                                # the doctor sees their own as "you"
        self.assertIn("Added by the patient", seen)                                          # and the patient's entries as the patient's

    def test_another_doctor_sees_the_first_doctors_name(self):
        approve(self.s)
        self.doc.post("/patient/1001/health/condition/", GIVEN["condition"])
        santos = self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview Medical Center")
        approve(self.s, santos.user_id)
        page = html(login(santos.user_id, PASSWORD).get("/patient/1001/?tab=medical"))
        self.assertRegex(page, r"Added by Dr. Reyes – [A-Z][a-z]{2} \d+, \d{4}")


class TheMedicalTab(HealthTestCase):
    def test_every_panel_has_add_in_its_header_and_items_open_their_prefilled_sheet(self):
        add_health_samples(self.s)
        page = html(self.pat.get("/record/"))
        for sheet in ("allergy-new", "condition-new", "medication-new", "vaccine-new"):
            self.assertIn(f'data-sheet="edit-{sheet}">Add</a>', page)
            self.assertIn(f'<dialog id="edit-{sheet}"', page)
        hypertension = self.item("condition", "Hypertension")
        self.assertIn(f'data-sheet="edit-condition-{hypertension.item_id}"', page)
        sheet = re.search(rf'<dialog id="edit-condition-{hypertension.item_id}".*?</dialog>', page, re.S).group(0)
        self.assertIn('value="Hypertension"', sheet)
        self.assertIn('<option value="Managed" selected>', sheet)
        self.assertIn('value="06/03/2024"', sheet)

    def test_the_sheets_are_named_for_their_kind_and_have_the_designs_boxes(self):
        page = html(self.pat.get("/record/"))
        expected = {"allergy": ("Allergy", ["Allergen", "Severity", "Reaction (optional)"]),
                    "condition": ("Condition", ["Name", "Status", "Diagnosed (optional)"]),
                    "medication": ("Medication", ["Name", "Dose", "How often", "Started (optional)"]),
                    "vaccine": ("Vaccine", ["Name", "Given on"])}
        for kind, (title, labels) in expected.items():
            sheet = re.search(rf'<dialog id="edit-{kind}-new".*?</dialog>', page, re.S).group(0)
            self.assertIn(f"<h2>{title}</h2>", sheet)
            self.assertEqual(re.findall(r"<label[^>]*>([^<]+)</label>", sheet), labels)
        severity = re.search(r'<dialog id="edit-allergy-new".*?</dialog>', page, re.S).group(0)
        self.assertEqual(re.findall(r'<option value="([^"]*)"', severity), ["Mild", "Moderate", "Severe"])
        status = re.search(r'<dialog id="edit-condition-new".*?</dialog>', page, re.S).group(0)
        self.assertEqual(re.findall(r'<option value="([^"]*)"', status), ["Active", "Managed", "Resolved"])

    def test_a_new_item_sheet_has_no_remove_but_an_existing_one_has_a_red_remove_that_asks_first(self):
        page = html(self.pat.get("/record/"))
        self.assertNotIn("Remove", re.search(r'<dialog id="edit-allergy-new".*?</dialog>', page, re.S).group(0))
        penicillin = self.item("allergy", "Penicillin")
        sheet = re.search(rf'<dialog id="edit-allergy-{penicillin.item_id}".*?</dialog>', page, re.S).group(0)
        self.assertIn(f'formaction="/health/{penicillin.item_id}/remove/"', sheet)
        self.assertIn('class="btn ghost red remove"', sheet)
        self.assertIn('data-confirm-title="Remove Penicillin?"', sheet)
        self.assertIn('name="item_id"', sheet)

    def test_a_doctor_sees_the_same_sheets_pointing_at_the_doctor_addresses(self):
        approve(self.s)
        page = html(self.doc.get("/patient/1001/?tab=medical"))
        self.assertIn('data-sheet="edit-allergy-new">Add</a>', page)
        penicillin = self.item("allergy", "Penicillin")
        sheet = re.search(rf'<dialog id="edit-allergy-{penicillin.item_id}".*?</dialog>', page, re.S).group(0)
        self.assertIn('action="/patient/1001/health/allergy/"', sheet)
        self.assertIn(f'formaction="/patient/1001/health/{penicillin.item_id}/remove/"', sheet)

    def test_a_doctor_with_a_locked_record_sees_no_sheets_at_all(self):
        page = html(self.doc.get("/patient/1001/"))
        self.assertNotIn("edit-allergy", page)
        self.assertNotIn("/health/", page)

    def test_severe_allergies_are_red_pills_and_moderate_ones_amber(self):
        add_health_samples(self.s)
        page = html(self.pat.get(MEDICAL))
        self.assertIn('<span class="atag">Severe</span>', page)
        self.assertIn('<span class="atag mod">Moderate</span>', page)

    def test_a_flash_reopens_the_sheet_of_the_item_that_failed(self):
        item = self.item("allergy", "Penicillin")
        r = self.pat.post("/health/allergy/", {"name": "", "severity": "Mild", "item_id": item.item_id, "next": MEDICAL})
        page = html(self.pat.get(r["Location"]))
        self.assertIn(f"sheet=edit-allergy-{item.item_id}", r["Location"])
        self.assertIn("Enter the allergen.", page)


class NotAddedAndAddLinks(HealthTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.post("/register/", {"role": "Patient", "name": "Zed Newcomer", "password": PASSWORD, "date_of_birth": BORN,
                                        "contact_number": "0917 000 7777"})

    def test_home_profile_and_my_record_say_not_added_with_a_link_that_opens_that_types_sheet(self):
        home = html(self.client.get("/dashboard/"))
        self.assertIn('data-sheet="edit-medication-new">Add</a>', home)
        self.assertIn('data-sheet="edit-vaccine-new">Add</a>', home)
        profile = html(self.client.get("/profile/"))
        for sheet in ("allergy-new", "condition-new", "medication-new", "vaccine-new"):
            self.assertIn(f'<span class="faint">Not added</span><a class="add-link" href="#" data-sheet="edit-{sheet}">Add</a>', profile)
            self.assertIn(f'<dialog id="edit-{sheet}"', profile)
        medical = html(self.client.get("/record/")).split('data-pane="medical"')[1]
        self.assertEqual(medical.split('data-pane="info"')[0].count('<p class="empty">Not added</p>'), 5)   # the five panels

    def test_nothing_says_none_recorded_or_not_recorded_any_more(self):
        for url in ("/dashboard/", "/profile/", "/record/"):
            page = html(self.client.get(url))
            self.assertNotIn("None recorded", page)
            self.assertNotIn("Not recorded", page)

    def test_given_on_appears_only_when_a_vaccine_exists(self):
        self.assertNotIn("Given on</span>", html(self.client.get("/profile/")))
        self.client.post("/health/vaccine/", {"name": "Flu shot", "date_on": "09/14/2026", "next": "/profile/"})
        profile = html(self.client.get("/profile/"))
        self.assertIn("Last vaccine</span><b>Flu shot</b>", profile)
        self.assertIn("Given on</span><b>Sep 14, 2026</b>", profile)

    def test_a_doctor_sees_not_added_and_add_links_only_while_the_record_is_open(self):
        newcomer = rows("SELECT patient_id FROM tb_patients WHERE mobile_number = '09170007777'")[0]["patient_id"]
        request = self.s.request_access(self.s.get_doctor(2001), newcomer)
        self.s.respond_to_request(request.request_id, newcomer, True)
        page = html(self.doc.get(f"/patient/{newcomer}/"))
        self.assertIn('<span class="faint">Not added</span><a class="add-link" href="#" data-sheet="edit-medication-new">Add</a>', page)
        self.assertIn(f'action="/patient/{newcomer}/health/medication/"', page)


if __name__ == "__main__":
    unittest.main()
