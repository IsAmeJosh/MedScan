"""Limits on what can be typed in: mobile numbers, passwords, dates of birth, field lengths, clear messages."""
import unittest
from datetime import date, timedelta

from django.test import Client

from logic.L_MedScan_System import MedScanSystem
from tests.helpers import BORN, PASSWORD, count, fresh_system, html, login
from tests.helpers import new_patient


class MobileNumbers(unittest.TestCase):
    def test_accepted_formats_are_saved_as_09(self):
        for typed in ["09171234567", "0917 123 4567", "0917-123-4567", "+639171234567", "+63 917 123 4567",
                      "639171234567", "63 917 123 4567", "(0917) 123 4567"]:
            self.assertEqual(MedScanSystem._check_contact(typed), "09171234567", typed)

    def test_blank_is_allowed(self):
        for blank in ["", None, "   "]:
            self.assertEqual(MedScanSystem._check_contact(blank), "")

    def test_everything_else_is_rejected(self):
        for typed in ["123", "0917123456", "091712345678", "08171234567", "+649171234567", "+6391712345678",
                      "abcdefghijk", "0917 123 456a", "+63 17 123 4567", "9171234567"]:
            with self.assertRaises(ValueError, msg=typed):
                MedScanSystem._check_contact(typed)

    def test_the_message_tells_the_user_what_to_type(self):
        with self.assertRaises(ValueError) as caught:
            MedScanSystem._check_contact("12345")
        self.assertEqual(str(caught.exception),
                         "Enter a valid mobile number, like 09171234567 or +63 917 123 4567.")

    def test_registering_and_editing_normalise_the_number(self):
        s = fresh_system(self)
        p = new_patient(s, "Ana", PASSWORD, "Female", BORN, contact_number="+63 928 111 2222")
        self.assertEqual(p.contact_number, "09281112222")
        s.update_patient_info(p.user_id, "", "", "", "", "0917-555-1234")
        self.assertEqual(s.get_patient(p.user_id).contact_number, "09175551234")


class Passwords(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_length_must_be_6_to_25(self):
        for bad in ["a", "12345", "p" * 26]:
            with self.assertRaises(ValueError, msg=bad):
                new_patient(self.s, "Ana", bad, "F", BORN)
            with self.assertRaises(ValueError, msg=bad):
                self.s.register_doctor("Cruz", bad, "ENT")
        new_patient(self.s, "Ana", "123456", "F", BORN)
        self.s.register_doctor("Cruz", "p" * 25, "ENT")

    def test_the_message_names_the_limits(self):
        with self.assertRaises(ValueError) as caught:
            new_patient(self.s, "Ana", "abc", "F", BORN)
        self.assertEqual(str(caught.exception), "Password must be 6 to 25 characters.")

    def test_nothing_is_saved_when_it_is_refused(self):
        before = count("patients")
        with self.assertRaises(ValueError):
            new_patient(self.s, "Ana", "abc", "F", BORN)
        self.assertEqual(count("patients"), before)


class DatesOfBirth(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_good_dates(self):
        new_patient(self.s, "Ana", PASSWORD, "F", date(1990, 5, 20))
        new_patient(self.s, "Bea", PASSWORD, "F", "1990-05-20")
        new_patient(self.s, "Cy", PASSWORD, "M", date.today())  # born today is a baby, not an error
        new_patient(self.s, "Di", PASSWORD, "F", "05/20/1990")  # month/day/year, as the form types it
        new_patient(self.s, "Ed", PASSWORD, "M", "5/2/1990")    # without the leading zeros

    def test_bad_dates(self):
        tomorrow = date.today() + timedelta(days=1)
        for bad, message in [("", "valid date"), (None, "valid date"), ("20/05/1990", "valid date"),
                             ("05/20/90", "valid date"), ("1990/05/20", "valid date"), ("02/30/2004", "valid date"),
                             ("1990-13-40", "valid date"), (tomorrow, "future"),
                             (date.today().replace(year=date.today().year - 121), "120 years")]:
            with self.assertRaises(ValueError, msg=str(bad)) as caught:
                new_patient(self.s, "Ana", PASSWORD, "F", bad)
            self.assertIn(message, str(caught.exception))


class FieldLengths(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doctor = self.s.get_doctor(2001)

    def test_registration_fields_stop_at_the_database_size(self):
        before = (count("patients"), count("doctors"))
        for call in [lambda: new_patient(self.s, "A" * 101, PASSWORD, "M", BORN),
                     lambda: new_patient(self.s, "Ana", PASSWORD, "M" * 21, BORN),
                     lambda: new_patient(self.s, "Ana", PASSWORD, "M", BORN, allergies="Peanuts, " + "x" * 201),
                     lambda: self.s.register_doctor("Cruz", PASSWORD, "S" * 101),
                     lambda: self.s.register_doctor("Cruz", PASSWORD, "ENT", "C" * 151)]:
            with self.assertRaises(ValueError):
                call()
        self.assertEqual((count("patients"), count("doctors")), before)  # nothing half-registered

    def test_the_limits_themselves_are_allowed(self):
        new_patient(self.s, "A" * 100, "p" * 25, "M" * 20, BORN, allergies="x" * 200)
        self.s.register_doctor("D" * 100, PASSWORD, "S" * 100, "C" * 150)

    def test_a_failed_edit_changes_nothing(self):
        before = self.s.get_patient(1001)
        with self.assertRaises(ValueError):
            self.s.update_patient_info(1001, "x" * 201, "", "", "O+", "09171234567")
        with self.assertRaises(ValueError):
            self.s.update_patient_info(1001, "Peanuts", "", "", "O+", "bad number")
        after = self.s.get_patient(1001)
        self.assertEqual((before.contact_number, before.record.allergies), (after.contact_number, after.record.allergies))

    def test_notes_and_emergency_reasons_have_limits(self):
        req = self.s.request_access(self.doctor, 1001)
        self.s.respond_to_request(req.request_id, 1001, True)
        self.assertIsNotNone(self.s.add_consultation(self.doctor, 1001, "n" * 5000))
        with self.assertRaises(ValueError):
            self.s.add_consultation(self.doctor, 1001, "n" * 5001)
        with self.assertRaises(ValueError):
            self.s.emergency_access(self.doctor, 1001, "r" * 501)
        self.assertEqual(count("emergency_logs"), 0)


class WebsiteMessages(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_registration_shows_the_message_and_keeps_what_was_typed(self):
        client = Client()
        r = client.post("/register/", {"role": "Patient", "name": "A" * 101, "password": PASSWORD,
                                       "date_of_birth": BORN})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Name is too long", html(r))
        r = client.post("/register/", {"role": "Patient", "name": "Zed", "password": PASSWORD,
                                       "date_of_birth": BORN, "contact_number": "12345"})
        self.assertIn("Enter a valid mobile number", html(r))
        self.assertIn('value="Zed"', html(r))
        r = client.post("/register/", {"role": "Patient", "name": "Zed", "password": "abc", "date_of_birth": BORN})
        self.assertIn("Password must be 6 to 25 characters.", html(r))
        r = client.post("/register/", {"role": "Patient", "name": "Zed", "password": PASSWORD,
                                       "date_of_birth": "not a date"})
        self.assertIn("Enter a valid date of birth like 04/04/2004", html(r))

    def test_the_form_has_browser_side_limits(self):
        page = html(Client().get("/register/?role=patient"))
        for hint in ['minlength="6"', 'maxlength="25"', 'name="date_of_birth"', 'data-format="date"', 'type="tel"']:
            self.assertIn(hint, page)

    def test_emergency_reason_too_long(self):
        doctor = login(2001, "doc123")
        r = doctor.post("/emergency/", {"patient_id": "1001", "reason": "r" * 501})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Emergency reason is too long", html(r))
        self.assertEqual(count("emergency_logs"), 0)

    def test_note_too_long(self):
        s = self.s
        req = s.request_access(s.get_doctor(2001), 1001)
        s.respond_to_request(req.request_id, 1001, True)
        doctor = login(2001, "doc123")
        r = doctor.post("/patient/1001/consult/", {"notes": "n" * 5001}, follow=True)
        self.assertIn("Consultation notes is too long", html(r))
        self.assertEqual(count("consultations"), 0)


if __name__ == "__main__":
    unittest.main()
