"""A person's own details: the edit sheets (one template, one view), what each saves, the checks with their plain messages, the
empty states of a new account, what a doctor sees, and the upgrade of a version 1 database."""
import re
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.test import Client

from data.D_Database import Database
from tests.helpers import BORN, PASSWORD, approve, fresh_system, html, login, new_patient, next_mobile, rows

INFO = "/record/?tab=info"
MEDICAL = "/record/?tab=medical"
MOBILE_MESSAGE = "Enter an 11-digit mobile number starting with 09, like 0917 123 4567."


def dialog(page, sheet_id):
    """The HTML of one sheet on a page."""
    return re.search(rf'<dialog id="{sheet_id}".*?</dialog>', page, re.S).group(0)


def labels(sheet_html):
    return re.findall(r"<label[^>]*>([^<]+)</label>", sheet_html)


class SheetsPageTestCase(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def save(self, client, sheet, fields, next_page=INFO, follow=True):
        return client.post(f"/details/{sheet}/", {**fields, "next": next_page}, follow=follow)

    def stored(self, patient_id=1001):
        return self.s.get_patient(patient_id)


class TheSheets(SheetsPageTestCase):
    def test_each_sheet_has_the_title_of_its_panel_and_only_that_panels_fields_in_order(self):
        record = html(self.pat.get("/record/"))
        expected = {
            "edit-basic": ("Basic info", ["Date of birth", "Sex", "Blood type", "Height", "Weight"]),
            "edit-contact": ("Contact", ["Mobile"]),
            "edit-emergency": ("Emergency contact", ["Name", "Relationship", "Mobile"]),
            "edit-surgeries": ("Past surgeries", ["Past surgeries"]),
        }
        for sheet_id, (title, fields) in expected.items():
            sheet = dialog(record, sheet_id)
            self.assertIn(f"<h2>{title}</h2>", sheet, sheet_id)
            self.assertEqual(labels(sheet), fields, sheet_id)
        profile = html(self.pat.get("/profile/"))
        personal = dialog(profile, "edit-personal")
        self.assertIn("<h2>Personal details</h2>", personal)
        self.assertEqual(labels(personal), ["Date of birth", "Sex", "Blood type", "Mobile"])
        self.assertEqual(labels(dialog(profile, "edit-emergency")), ["Name", "Relationship", "Mobile"])

    def test_age_is_shown_but_never_a_box(self):
        for page in (html(self.pat.get("/record/")), html(self.pat.get("/profile/"))):
            self.assertIn("<span>Age</span>", page)
            self.assertNotIn('name="age"', page)
            self.assertNotIn(">Age</label>", page)

    def test_the_boxes_start_filled_with_what_is_saved(self):
        record = html(self.pat.get("/record/"))
        basic = dialog(record, "edit-basic")
        self.assertIn('value="03/14/1996"', basic)
        self.assertIn('<option value="Male" selected>', basic)
        self.assertIn('<option value="O+" selected>', basic)
        self.assertIn('value="170"', basic)
        self.assertIn('value="68"', basic)
        self.assertIn('value="0917 123 4567"', dialog(record, "edit-contact"))
        emergency = dialog(record, "edit-emergency")
        for value in ("Maria Dela Cruz", "Mother", "0918 765 4321"):
            self.assertIn(f'value="{value}"', emergency)

    def test_cancel_closes_the_sheet_without_saving_and_save_is_the_only_button_that_posts(self):
        sheet = dialog(html(self.pat.get("/record/")), "edit-basic")
        self.assertIn('<button type="button" class="btn lg cancel" data-close>Cancel</button>', sheet)
        self.assertEqual(len(re.findall(r'type="submit"', sheet)), 1)

    def test_the_old_combined_sheets_are_gone(self):
        for url in ("/record/", "/profile/"):
            page = html(self.pat.get(url))
            self.assertNotIn("edit-sheet", page)
            self.assertNotIn("contact-sheet", page)
            self.assertNotIn("Edit contact info", page)
            self.assertNotIn("Edit my information", page)
        self.assertEqual(self.pat.get("/record/edit/").status_code, 404)
        self.assertEqual(self.pat.get("/profile/contact/").status_code, 404)


class Saving(SheetsPageTestCase):
    def test_every_sheet_saves_and_the_page_shows_it_with_the_teal_saved_message(self):
        cases = [
            ("basic", {"date_of_birth": "04/05/1994", "sex": "Female", "blood_type": "AB-", "height_cm": "165", "weight_kg": "58.5"}, INFO),
            ("contact", {"contact_number": "0928 111 2222"}, INFO),
            ("emergency", {"emergency_name": "Rosa Cruz", "emergency_relationship": "Sister", "emergency_mobile": "0919 222 3333"}, INFO),
            ("surgeries", {"surgeries": "Tonsillectomy"}, MEDICAL),
        ]
        for sheet, fields, page in cases:
            response = self.save(self.pat, sheet, fields, page)
            body = html(response)
            self.assertIn('class="toast success"', body, sheet)
            self.assertIn("<span>Saved</span>", body, sheet)
        patient = self.stored()
        self.assertEqual((patient.date_of_birth, patient.sex, patient.record.blood_type), (date(1994, 4, 5), "Female", "AB-"))
        self.assertEqual((patient.height_cm, patient.weight_kg), (165, Decimal("58.5")))
        self.assertEqual(patient.contact_number, "09281112222")
        self.assertEqual((patient.emergency_name, patient.emergency_relationship, patient.emergency_mobile),
                         ("Rosa Cruz", "Sister", "09192223333"))
        self.assertEqual(patient.record.surgeries, ["Tonsillectomy"])

    def test_the_profile_sheets_save_too(self):
        self.save(self.pat, "personal", {"date_of_birth": "04/05/1994", "sex": "Female", "blood_type": "A+", "contact_number": "0928 111 2222"}, "/profile/")
        self.save(self.pat, "emergency", {"emergency_name": "Rosa Cruz", "emergency_relationship": "Sister", "emergency_mobile": ""}, "/profile/")
        patient = self.stored()
        self.assertEqual((patient.date_of_birth, patient.sex, patient.record.blood_type, patient.contact_number),
                         (date(1994, 4, 5), "Female", "A+", "09281112222"))
        self.assertEqual((patient.emergency_name, patient.emergency_mobile), ("Rosa Cruz", ""))
        body = html(self.pat.get("/profile/"))
        self.assertIn("Date of birth</span><b>Apr 5, 1994</b>", body)
        self.assertIn("Sex</span><b>Female</b>", body)
        self.assertIn("Name</span><b>Rosa Cruz</b>", body)

    def test_a_sheet_saves_only_the_fields_it_is_given(self):
        before = self.stored()
        self.save(self.pat, "contact", {"contact_number": "0928 111 2222"})
        after = self.stored()
        self.assertEqual((after.height_cm, after.weight_kg, after.emergency_name, after.record.allergies, after.record.blood_type),
                         (before.height_cm, before.weight_kg, before.emergency_name, before.record.allergies, before.record.blood_type))
        self.save(self.pat, "basic", {"date_of_birth": "03/14/1996", "sex": "Male", "blood_type": "O+", "height_cm": "172", "weight_kg": ""})
        after = self.stored()
        self.assertEqual((after.height_cm, after.weight_kg), (172, None))              # a blank clears an optional detail
        self.assertEqual((after.contact_number, after.emergency_mobile), ("09281112222", "09187654321"))
        self.save(self.pat, "surgeries", {"surgeries": "Tonsillectomy"}, MEDICAL)
        after = self.stored()
        self.assertEqual((after.record.allergies, after.record.surgeries), (["Penicillin"], ["Tonsillectomy"]))   # the health items stay

    def test_a_weight_with_a_decimal_and_a_whole_weight_are_shown_nicely(self):
        self.save(self.pat, "basic", {"date_of_birth": "03/14/1996", "sex": "Male", "blood_type": "O+", "height_cm": "170", "weight_kg": "68.5"})
        self.assertIn("Weight</span><b>68.5 kg</b>", html(self.pat.get("/record/")))
        self.save(self.pat, "basic", {"date_of_birth": "03/14/1996", "sex": "Male", "blood_type": "O+", "height_cm": "170", "weight_kg": "70"})
        self.assertIn("Weight</span><b>70 kg</b>", html(self.pat.get("/record/")))

    def test_age_is_worked_out_from_the_date_of_birth(self):
        years = (date.today() - timedelta(days=365 * 30 + 8)).strftime("%m/%d/%Y")
        self.save(self.pat, "basic", {"date_of_birth": years, "sex": "Male", "blood_type": "O+", "height_cm": "", "weight_kg": ""})
        self.assertIn("<span>Age</span><b>30</b>", html(self.pat.get("/record/")))

    def test_the_doctors_work_details_sheet_saves_their_mobile_number(self):
        body = html(self.save(self.doc, "work", {"contact_number": "0918 777 8888"}, "/profile/"))
        self.assertIn("<span>Saved</span>", body)
        self.assertEqual(self.s.get_doctor(2001).contact_number, "09187778888")
        self.assertIn("Mobile</span><b>0918 777 8888</b>", body)

    def test_a_form_cannot_send_the_person_to_another_site_or_edit_what_the_sheet_does_not_have(self):
        r = self.pat.post("/details/contact/", {"contact_number": "0928 111 2222", "next": "https://example.com/"})
        self.assertEqual(r["Location"], "/profile/")
        before = self.stored().height_cm
        self.pat.post("/details/contact/", {"contact_number": "0928 111 2223", "height_cm": "99", "next": INFO})
        self.assertEqual(self.stored().height_cm, before)                              # only the sheet's own fields count
        self.assertEqual(self.pat.post("/details/nonsense/", {"next": INFO})["Location"], "/profile/")
        self.assertEqual(self.pat.get("/details/contact/")["Location"], "/profile/")   # a page address alone changes nothing
        self.assertEqual(Client().post("/details/contact/", {"contact_number": "0928 111 2222"})["Location"], "/")


class Checks(SheetsPageTestCase):
    def assert_refused(self, sheet, fields, field, message, next_page=INFO):
        """The save is refused: nothing changes, the person is sent back to the page with that sheet open, and the message
        is under the right box with what they typed still in it."""
        before = self.stored()
        r = self.save(self.pat, sheet, fields, next_page, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith(f"sheet=edit-{sheet}"), r["Location"])
        page = html(self.pat.get(r["Location"]))
        box = dialog(page, f"edit-{sheet}")
        wrapped = re.search(rf'<div class="field has-error">\s*<label for="edit-{sheet}-{field}">.*?<p class="field-error" role="alert">([^<]+)</p>', box, re.S)
        self.assertIsNotNone(wrapped, f"{field}: {message}")
        self.assertEqual(wrapped.group(1).replace("&#x27;", "'"), message)
        typed = fields[field]
        if typed and field not in ("blood_type", "sex"):                               # a list box has no typed text to keep
            self.assertIn(f'value="{typed}"', box)                                    # what they typed is kept
        after = self.stored()
        self.assertEqual((after.height_cm, after.weight_kg, after.contact_number, after.sex, after.date_of_birth),
                         (before.height_cm, before.weight_kg, before.contact_number, before.sex, before.date_of_birth))
        self.assertNotIn("error", html(self.pat.get(next_page)).split('<div class="toasts"')[1].split("</div>")[0])   # not shown twice
        return page

    BASIC = {"date_of_birth": "03/14/1996", "sex": "Male", "blood_type": "O+", "height_cm": "170", "weight_kg": "68"}

    def test_mobile_is_eleven_digits_starting_with_09(self):
        for bad in ("12", "0917 123 456", "0817 123 4567", "0917 123 45678", "abcdefghijk"):
            self.assert_refused("contact", {"contact_number": bad}, "contact_number", MOBILE_MESSAGE)
        self.assert_refused("contact", {"contact_number": ""}, "contact_number", "Enter your mobile number.")
        self.assert_refused("emergency", {"emergency_name": "A", "emergency_relationship": "B", "emergency_mobile": "555"},
                            "emergency_mobile", MOBILE_MESSAGE)

    def test_a_mobile_number_belongs_to_one_account(self):
        other = new_patient(self.s, "Other Patient", PASSWORD, "Female", BORN, contact_number="09285550000")
        self.assert_refused("contact", {"contact_number": "0928 555 0000"}, "contact_number",
                            "That mobile number is already used by another account.")
        self.assertEqual(other.contact_number, "09285550000")

    def test_date_of_birth_cannot_be_in_the_future_or_made_up(self):
        tomorrow = (date.today() + timedelta(days=1)).strftime("%m/%d/%Y")
        self.assert_refused("basic", {**self.BASIC, "date_of_birth": tomorrow}, "date_of_birth", "Date of birth cannot be in the future.")
        self.assert_refused("basic", {**self.BASIC, "date_of_birth": "13/45/2000"}, "date_of_birth",
                            "Enter a valid date of birth like 04/04/2004 (month/day/year).")
        self.assert_refused("personal", {"date_of_birth": tomorrow, "sex": "Male", "blood_type": "O+", "contact_number": "09171234567"},
                            "date_of_birth", "Date of birth cannot be in the future.", "/profile/")

    def test_height_is_50_to_250_centimetres(self):
        for bad in ("49", "251", "0", "-170"):
            self.assert_refused("basic", {**self.BASIC, "height_cm": bad}, "height_cm", "Height must be between 50 and 250 cm.")
        self.assert_refused("basic", {**self.BASIC, "height_cm": "tall"}, "height_cm", "Enter your height as a number of centimetres, like 170.")
        self.assert_refused("basic", {**self.BASIC, "height_cm": "170.5"}, "height_cm", "Enter your height as a whole number of centimetres, like 170.")
        for good, expected in (("50", 50), ("250", 250), ("170 cm", 170)):
            self.save(self.pat, "basic", {**self.BASIC, "height_cm": good})
            self.assertEqual(self.stored().height_cm, expected)

    def test_weight_is_2_to_300_kilograms(self):
        for bad in ("1.9", "301", "0"):
            self.assert_refused("basic", {**self.BASIC, "weight_kg": bad}, "weight_kg", "Weight must be between 2 and 300 kg.")
        self.assert_refused("basic", {**self.BASIC, "weight_kg": "heavy"}, "weight_kg", "Enter your weight as a number of kilograms, like 68.")
        for good, expected in (("2", Decimal("2.0")), ("300", Decimal("300.0")), ("68.5", Decimal("68.5"))):
            self.save(self.pat, "basic", {**self.BASIC, "weight_kg": good})
            self.assertEqual(self.stored().weight_kg, expected)

    def test_blood_type_is_one_of_the_eight_or_not_set_and_sex_is_male_or_female(self):
        self.assert_refused("basic", {**self.BASIC, "blood_type": "Z+"}, "blood_type", "Choose a blood type from the list.")
        self.assert_refused("basic", {**self.BASIC, "sex": "Other"}, "sex", "Choose Male or Female.")
        for blood in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", ""):
            self.save(self.pat, "basic", {**self.BASIC, "blood_type": blood})
            self.assertEqual(self.stored().record.blood_type, blood)
        page = html(self.pat.get("/record/"))
        options = re.findall(r'<option value="([^"]*)"', dialog(page, "edit-basic"))
        self.assertEqual(options, ["Male", "Female", "", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])

    def test_names_that_are_too_long_are_refused_in_plain_words(self):
        self.assert_refused("emergency", {"emergency_name": "A" * 101, "emergency_relationship": "", "emergency_mobile": ""},
                            "emergency_name", "Emergency contact name is too long (at most 100 characters).")

    def test_every_wrong_box_gets_its_own_message_and_nothing_is_saved_when_any_is_wrong(self):
        r = self.save(self.pat, "basic", {"date_of_birth": "13/45/2000", "sex": "Other", "blood_type": "O+", "height_cm": "20", "weight_kg": "68"}, follow=False)
        box = dialog(html(self.pat.get(r["Location"])), "edit-basic")
        self.assertEqual(len(re.findall(r'class="field-error"', box)), 3)
        self.assertEqual(self.stored().height_cm, 170)                                   # the one good box was not saved either

    def test_the_messages_wait_for_one_page_only(self):
        r = self.save(self.pat, "contact", {"contact_number": "12"}, follow=False)
        self.assertIn("field-error", html(self.pat.get(r["Location"])))
        self.assertNotIn("field-error", html(self.pat.get(r["Location"])))


class NewAccounts(unittest.TestCase):
    """A freshly registered patient has nothing but the basics and adds everything from empty."""

    def setUp(self):
        self.s = fresh_system(self)
        self.client = Client()
        self.client.post("/register/", {"role": "Patient", "name": "Zed Newcomer", "password": PASSWORD, "date_of_birth": BORN,
                                        "contact_number": "0917 000 9999"})

    def page(self, url):
        return html(self.client.get(url))

    def test_missing_details_say_not_added_with_an_add_link_that_opens_the_panels_sheet(self):
        info = self.page("/record/").split('data-pane="info"')[1]
        for label in ("Blood type", "Height", "Weight"):
            self.assertRegex(info, rf'<span>{label}</span><b><span class="faint">Not added</span><a class="add-link" href="#" data-sheet="edit-basic">Add</a></b>')
        profile = self.page("/profile/")
        self.assertRegex(profile, r'<span>Blood type</span><b><span class="faint">Not added</span><a class="add-link" href="#" data-sheet="edit-personal">Add</a></b>')

    def test_an_empty_emergency_contact_panel_has_its_own_empty_state_and_an_add_header_link(self):
        for url, sheet in (("/record/", "edit-emergency"), ("/profile/", "edit-emergency")):
            page = self.page(url)
            panel = page.split("<h2>Emergency contact</h2>")[1].split("</div>\n        </div>")[0] if url == "/record/" else page.split("<h2>Emergency contact</h2>")[1]
            self.assertIn(f'data-sheet="{sheet}">Add</a>', page.split("<h2>Emergency contact</h2>")[1][:120])
            self.assertIn("No emergency contact yet", panel)
            self.assertNotIn("Add emergency contact", page)                           # the one Add link in the header is the only way in
            self.assertNotIn("Not added", panel.split("</div>")[0])

    def test_adding_everything_from_empty_then_shows_the_values_and_edit_links(self):
        self.client.post("/details/basic/", {"date_of_birth": "05/20/1990", "sex": "Male", "blood_type": "B+", "height_cm": "180", "weight_kg": "75", "next": INFO})
        self.client.post("/details/emergency/", {"emergency_name": "Ana Newcomer", "emergency_relationship": "Wife", "emergency_mobile": "0920 111 2222", "next": INFO})
        self.client.post("/health/allergy/", {"name": "Dust", "severity": "Mild", "next": MEDICAL})
        self.client.post("/health/allergy/", {"name": "Pollen", "severity": "Mild", "next": MEDICAL})
        self.client.post("/health/medication/", {"name": "Cetirizine", "dose": "10 mg", "frequency": "daily", "next": MEDICAL})
        self.client.post("/details/surgeries/", {"surgeries": "Appendectomy", "next": MEDICAL})
        info = self.page("/record/").split('data-pane="info"')[1]
        for text in ("Blood type</span><b>B+</b>", "Height</span><b>180 cm</b>", "Weight</span><b>75 kg</b>", "Name</span><b>Ana Newcomer</b>",
                     "Relationship</span><b>Wife</b>", "Mobile</span><b>0920 111 2222</b>"):
            self.assertIn(text, info)
        self.assertNotIn("Not added", info)
        self.assertNotIn("No emergency contact yet", info)
        self.assertIn('data-sheet="edit-emergency">Edit</a>', info)                      # the header link goes back to Edit
        self.assertNotIn('data-sheet="edit-emergency">Add</a>', info)
        profile = self.page("/profile/")
        self.assertIn("Blood type</span><b>B+</b>", profile)
        self.assertIn('data-sheet="edit-emergency">Edit</a>', profile)
        medical = self.page("/record/").split('data-pane="medical"')[1]
        for text in ("Dust", "Pollen", "Cetirizine", "Appendectomy"):
            self.assertIn(text, medical)
        self.assertIn('data-sheet="edit-surgeries">Edit</a>', medical)
        self.assertIn('data-sheet="edit-allergy-new">Add</a>', medical)             # the header Add stays for the health items

    def test_an_empty_list_offers_add_and_a_filled_one_offers_edit(self):
        medical = self.page("/record/").split('data-pane="medical"')[1]
        for sheet in ("allergy-new", "medication-new", "condition-new", "vaccine-new", "surgeries"):
            self.assertIn(f'data-sheet="edit-{sheet}">Add</a>', medical)

    def test_a_new_account_shows_nobody_elses_details(self):
        body = self.page("/record/") + self.page("/profile/")
        for borrowed in ("Maria Dela Cruz", "170 cm", "68 kg", "0918 765 4321"):
            self.assertNotIn(borrowed, body)


class WhatADoctorSees(SheetsPageTestCase):
    def test_the_doctor_sees_the_saved_details_right_away(self):
        approve(self.s)
        before = html(self.doc.get("/patient/1001/")).split('data-pane="info"')[1]
        self.assertIn("Height</span><b>170 cm</b>", before)
        self.save(self.pat, "basic", {"date_of_birth": "03/14/1996", "sex": "Male", "blood_type": "A-", "height_cm": "172", "weight_kg": "70.5"})
        self.save(self.pat, "contact", {"contact_number": "0928 111 2222"})
        self.save(self.pat, "emergency", {"emergency_name": "Rosa Cruz", "emergency_relationship": "Sister", "emergency_mobile": "0919 222 3333"})
        page = html(self.doc.get("/patient/1001/"))
        info = page.split('data-pane="info"')[1]
        for text in ("Height</span><b>172 cm</b>", "Weight</span><b>70.5 kg</b>", "Blood type</span><b>A-</b>", "Mobile</span><b>0928 111 2222</b>",
                     "Name</span><b>Rosa Cruz</b>", "Relationship</span><b>Sister</b>", "Mobile</span><b>0919 222 3333</b>"):
            self.assertIn(text, info)
        self.assertIn("&middot; A-</p>", page)                                           # the header line shows the new blood type
        self.assertNotIn("data-sheet", info)                                             # a doctor cannot edit the patient's details

    def test_a_doctor_sees_not_added_for_what_a_patient_has_not_entered(self):
        approve(self.s)
        client = Client()
        client.post("/register/", {"role": "Patient", "name": "Zed Newcomer", "password": PASSWORD, "date_of_birth": BORN, "contact_number": "0917 000 9998"})
        newcomer = rows("SELECT patient_id FROM tb_patients WHERE mobile_number = '09170009998'")[0]["patient_id"]
        request = self.s.request_access(self.s.get_doctor(2001), newcomer)
        self.s.respond_to_request(request.request_id, newcomer, True)
        info = html(self.doc.get(f"/patient/{newcomer}/")).split('data-pane="info"')[1]
        self.assertIn("Height</span><b><span class=\"faint\">Not added</span></b>", info)
        self.assertIn("No emergency contact yet", info)
        self.assertNotIn("Add</a>", info)


class PhoneFix(unittest.TestCase):
    def test_the_allergy_banner_has_room_above_and_inside_on_a_phone(self):
        css = (Path(__file__).resolve().parent.parent / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width:760px){.allergy{padding:14px}.head + .allergy{margin-top:16px}}", css)
        self.assertIn(".allergy{display:flex;gap:12px;align-items:flex-start;background:var(--red-tint)", css)


class UpgradeFromVersionOne(unittest.TestCase):
    """A version 1 database is upgraded in place and keeps its data; the demo patient gets the values from the design."""

    NAME = "db_medscan_migration_test"

    def setUp(self):
        self.db = Database.from_environment(name=self.NAME)
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS tb_patients")
                cur.execute("DROP TABLE IF EXISTS tb_schema_version")
                cur.execute("CREATE TABLE tb_schema_version (version INT NOT NULL PRIMARY KEY)")
                cur.execute("INSERT INTO tb_schema_version VALUES (1)")
                cur.execute("CREATE TABLE tb_patients (patient_id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL, "
                            "mobile_number VARCHAR(11) NOT NULL) AUTO_INCREMENT=1001")
                cur.execute("INSERT INTO tb_patients (patient_id, name, mobile_number) VALUES "
                            "(1001, 'Juan Dela Cruz', '09171234567'), (1002, 'Someone Else', '09170000001')")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{self.NAME}`")
            conn.commit()
        finally:
            conn.close()

    def upgrade(self):
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                self.db._upgrade_1_to_2(cur)

    def test_the_columns_arrive_the_demo_patient_is_filled_and_the_version_moves_on(self):
        self.upgrade()
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM tb_patients ORDER BY patient_id")
            juan, other = cur.fetchall()
            cur.execute("SELECT version FROM tb_schema_version")
            version = cur.fetchone()["version"]
        self.assertEqual((juan["height_cm"], juan["weight_kg"], juan["emergency_name"], juan["emergency_relationship"], juan["emergency_mobile"]),
                         (170, Decimal("68.0"), "Maria Dela Cruz", "Mother", "09187654321"))
        self.assertEqual((other["height_cm"], other["weight_kg"], other["emergency_name"]), (None, None, ""))   # nobody else is touched
        self.assertEqual(version, 2)

    def test_running_it_again_is_harmless_and_does_not_overwrite_what_a_patient_entered(self):
        self.upgrade()
        with self.db.cursor() as cur:
            cur.execute("UPDATE tb_patients SET height_cm = 180, emergency_name = 'Own Choice' WHERE patient_id = 1001")
        self.upgrade()
        with self.db.cursor() as cur:
            cur.execute("SELECT height_cm, emergency_name FROM tb_patients WHERE patient_id = 1001")
            row = cur.fetchone()
        self.assertEqual((row["height_cm"], row["emergency_name"]), (180, "Own Choice"))

    def test_the_new_columns_refuse_a_height_or_weight_outside_the_range(self):
        self.upgrade()
        import pymysql
        for column, value in (("height_cm", 49), ("height_cm", 251), ("weight_kg", 1.9), ("weight_kg", 301)):
            with self.assertRaises(pymysql.err.Error, msg=f"{column}={value}"):
                with self.db.cursor() as cur:
                    cur.execute(f"UPDATE tb_patients SET {column} = %s WHERE patient_id = 1002", (value,))


class UpgradeFromVersionTwo(unittest.TestCase):
    """A version 2 database keeps its allergies and medications: they move into the health items as the patient's own."""

    NAME = "db_medscan_migration_test_v3"

    def setUp(self):
        self.db = Database.from_environment(name=self.NAME)
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE tb_schema_version (version INT NOT NULL PRIMARY KEY)")
                cur.execute("INSERT INTO tb_schema_version VALUES (2)")
                cur.execute("CREATE TABLE tb_patients (patient_id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL) AUTO_INCREMENT=1001")
                cur.execute("CREATE TABLE tb_doctors (doctor_id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL) AUTO_INCREMENT=2001")
                cur.execute("CREATE TABLE tb_medical_items (item_id INT AUTO_INCREMENT PRIMARY KEY, patient_id INT NOT NULL, "
                            "item_type VARCHAR(20) NOT NULL, item_name VARCHAR(200) NOT NULL)")
                cur.execute("INSERT INTO tb_patients (patient_id, name) VALUES (1001, 'Juan Dela Cruz'), (1002, 'Someone Else')")
                cur.execute("INSERT INTO tb_medical_items (patient_id, item_type, item_name) VALUES "
                            "(1001, 'allergy', 'Penicillin'), (1001, 'surgery', 'Appendectomy'), (1002, 'allergy', 'Dust'), "
                            "(1002, 'medication', 'Metformin')")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{self.NAME}`")
            conn.commit()
        finally:
            conn.close()

    def upgrade(self):
        with self.db.unit_of_work():
            with self.db.cursor() as cur:
                self.db._upgrade_2_to_3(cur)

    def test_allergies_and_medications_move_surgeries_stay_and_the_version_moves_on(self):
        self.upgrade()
        with self.db.cursor() as cur:
            cur.execute("SELECT patient_id, kind, name, severity, reaction, added_by_role, added_by_id, added_by_name "
                        "FROM tb_health_items ORDER BY item_id")
            items = cur.fetchall()
            cur.execute("SELECT item_type, item_name FROM tb_medical_items ORDER BY item_id")
            left = cur.fetchall()
            cur.execute("SELECT version FROM tb_schema_version")
            version = cur.fetchone()["version"]
        self.assertEqual([(i["patient_id"], i["kind"], i["name"]) for i in items],
                         [(1001, "allergy", "Penicillin"), (1002, "allergy", "Dust"), (1002, "medication", "Metformin")])
        self.assertEqual((items[0]["severity"], items[0]["reaction"]), ("Severe", "Hives, ER visit Jan 12, 2025"))   # the demo patient's details
        self.assertEqual(items[1]["severity"], "Mild")                                   # an old allergy starts as Mild
        self.assertIsNone(items[2]["severity"])                                          # a medication has none
        self.assertEqual((items[1]["added_by_role"], items[1]["added_by_id"], items[1]["added_by_name"]), ("patient", 1002, "Someone Else"))
        self.assertEqual([(r["item_type"], r["item_name"]) for r in left], [("surgery", "Appendectomy")])
        self.assertEqual(version, 3)

    def test_running_it_again_changes_nothing(self):
        self.upgrade()
        self.upgrade()
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tb_health_items")
            self.assertEqual(cur.fetchone()["n"], 3)


if __name__ == "__main__":
    unittest.main()
