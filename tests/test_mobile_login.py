"""The mobile number: required for patients, one per account, and a second way to log in."""
import threading
import unittest

from django.test import Client

from logic.L_MedScan_System import MedScanSystem
from tests.helpers import BORN, PASSWORD, committed_system, count, fresh_system, html, login, new_patient, next_mobile


class RulesInTheLogic(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_a_patient_must_have_a_mobile_number(self):
        for blank in ["", "   ", None]:
            with self.assertRaises(ValueError) as caught:
                self.s.register_patient("Ana", PASSWORD, "F", BORN, contact_number=blank)
            self.assertEqual(str(caught.exception), "Enter your mobile number.")

    def test_doctors_do_not_need_one(self):
        self.s.register_doctor("Cruz", PASSWORD, "ENT")

    def test_one_number_one_account_however_it_is_written(self):
        new_patient(self.s, "Ana", PASSWORD, "F", BORN, contact_number="0917 000 1111")
        before = count("tb_patients")
        for typed in ["09170001111", "+63 917 000 1111", "63 917 000 1111", "(0917) 000-1111"]:
            with self.assertRaises(ValueError) as caught:
                self.s.register_patient("Bea", PASSWORD, "F", BORN, contact_number=typed)
            self.assertEqual(str(caught.exception), "That mobile number is already used by another account.")
        self.assertEqual(count("tb_patients"), before)

    def test_changing_your_number_checks_the_others_but_not_yourself(self):
        ana = new_patient(self.s, "Ana", PASSWORD, "F", BORN, contact_number="09170001111")
        bea = new_patient(self.s, "Bea", PASSWORD, "F", BORN, contact_number="09170002222")
        with self.assertRaises(ValueError):
            self.s.update_patient_info(bea.user_id, "", "", "", "", "0917 000 1111")   # Ana's
        self.assertEqual(self.s.get_patient(bea.user_id).contact_number, "09170002222")
        self.s.update_patient_info(bea.user_id, "", "", "", "", "0917 000 2222")        # her own, spaced: fine
        self.s.update_patient_info(bea.user_id, "", "", "", "", "0917 000 3333")        # a new, free one
        new_patient(self.s, "Cy", PASSWORD, "M", BORN, contact_number="09170002222")    # Bea's old one is free now
        self.assertEqual(self.s.get_patient(ana.user_id).contact_number, "09170001111")

    def test_a_patient_cannot_remove_their_number(self):
        with self.assertRaises(ValueError) as caught:
            self.s.update_patient_info(1001, "", "", "", "", "")
        self.assertEqual(str(caught.exception), "Enter your mobile number.")
        self.assertEqual(self.s.get_patient(1001).contact_number, "09171234567")

    def test_a_refused_edit_changes_nothing_else(self):
        other = new_patient(self.s, "Ana", PASSWORD, "F", BORN, contact_number="09170001111")
        with self.assertRaises(ValueError):
            self.s.update_patient_info(1001, "Peanuts", "", "", "A+", "0917 000 1111")
        juan = self.s.get_patient(1001)
        self.assertEqual((juan.record.allergies, juan.record.blood_type), (["Penicillin"], "O+"))
        self.assertEqual(self.s.get_patient(other.user_id).contact_number, "09170001111")

    def test_normalize_mobile(self):
        for typed in ["09171234567", "0917 123 4567", "+63 917 123 4567", "63 917 123 4567", "(0917)-123-4567"]:
            self.assertEqual(MedScanSystem.normalize_mobile(typed), "09171234567", typed)
        for typed in ["", None, "1001", "PT-2026-01001", "0917", "12345678901", "+64 917 123 4567"]:
            self.assertIsNone(MedScanSystem.normalize_mobile(typed), typed)


class WhatTheLoginBoxAccepts(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_an_id_a_full_id_or_a_mobile_number(self):
        juan = self.s.get_patient(1001)
        for typed in ["1001", juan.display_id, juan.display_id.lower(), "0917 123 4567", "09171234567",
                      "+63 917 123 4567", "639171234567", " 1001 "]:
            self.assertEqual(self.s.resolve_login(typed), 1001, typed)
        self.assertEqual(self.s.resolve_login("2001"), 2001)
        self.assertEqual(self.s.resolve_login(self.s.get_doctor(2001).display_id), 2001)

    def test_nothing_that_matches(self):
        for typed in ["", None, "abc", "0917 999 9999", "+63 917 999 9999"]:
            self.assertIsNone(self.s.resolve_login(typed), typed)

    def test_a_mobile_number_is_never_mistaken_for_an_id(self):
        # the last digits of a number look like an ID: it must be treated as a number, not as ID 4567
        new_patient(self.s, "Ana", PASSWORD, "F", BORN, contact_number="09170004567")
        self.assertNotEqual(self.s.resolve_login("0917 000 4567"), 4567)
        self.assertEqual(self.s.get_patient(self.s.resolve_login("0917 000 4567")).name, "Ana")

    def test_two_patients_each_log_in_with_their_own_number(self):
        ana = new_patient(self.s, "Ana", PASSWORD, "F", BORN, contact_number="09170001111")
        bea = new_patient(self.s, "Bea", PASSWORD, "F", BORN, contact_number="09170002222")
        self.assertEqual(self.s.resolve_login("0917 000 1111"), ana.user_id)
        self.assertEqual(self.s.resolve_login("0917 000 2222"), bea.user_id)


class LoggingInOnThePage(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def log_in(self, typed, password="pat123"):
        return Client().post("/", {"user_id": typed, "password": password})

    def test_the_seed_patient_logs_in_with_the_mobile_number(self):
        for typed in ["0917 123 4567", "09171234567", "+63 917 123 4567"]:
            r = self.log_in(typed)
            self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/"), typed)

    def test_the_session_belongs_to_the_right_person(self):
        client = Client()
        client.post("/", {"user_id": "0917 123 4567", "password": "pat123"})
        self.assertIn("Juan Dela Cruz", html(client.get("/dashboard/")))

    def test_a_wrong_password_or_unknown_number_gives_the_same_message(self):
        for typed, password in [("0917 123 4567", "nope"), ("0917 999 9999", "pat123"), ("0917 999 9999", "nope")]:
            r = self.log_in(typed, password)
            self.assertEqual(r.status_code, 200)
            self.assertIn("Wrong ID number or password.", html(r))   # nothing says which part was wrong

    def test_a_doctor_still_logs_in_with_the_id(self):
        self.assertEqual(self.log_in("2001", "doc123")["Location"], "/dashboard/")

    def test_the_login_box_says_what_it_accepts(self):
        page = html(Client().get("/"))
        self.assertIn("ID or mobile number", page)
        self.assertIn('autocomplete="username"', page)


class TwoPeopleTakingTheSameNumber(unittest.TestCase):
    def test_only_one_of_several_simultaneous_registrations_wins(self):
        s = committed_system(self)
        results = []

        def register(n):
            try:
                s.register_patient(f"Racer {n}", PASSWORD, "F", BORN, contact_number="0917 555 0000")
                results.append("ok")
            except ValueError as error:
                results.append(str(error))

        threads = [threading.Thread(target=register, args=(n,)) for n in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(set(results) - {"ok"}, {"That mobile number is already used by another account."})
        self.assertEqual(count("tb_patients", "mobile_number = '09175550000'"), 1)


if __name__ == "__main__":
    unittest.main()
