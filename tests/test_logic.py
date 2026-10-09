"""Unit tests for the rules inside MedScanSystem (no website, no database)."""
import os
import tempfile
import unittest

from data.D_Memory_Store import MemoryStore
from data.D_Pickle_Store import PickleStore
from logic.L_MedScan_System import MedScanSystem
from tests.helpers import fresh_system


class AccessRules(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system()
        self.doctor, self.patient = self.s.doctors[2001], self.s.patients[1001]

    def approve(self):
        req = self.s.request_access(self.doctor, 1001)
        self.s.respond_to_request(req.request_id, 1001, True)
        return req

    def test_no_access_before_approval(self):
        self.assertEqual(self.s.access_status(2001, 1001), "none")
        self.assertIsNone(self.s.add_consultation(self.doctor, 1001, "too early"))
        self.assertIsNone(self.s.open_record(self.doctor, 1001))

    def test_approval_allows_notes_and_viewing(self):
        self.approve()
        self.assertEqual(self.s.access_status(2001, 1001), "approved")
        self.assertIsNotNone(self.s.add_consultation(self.doctor, 1001, "fever"))
        self.assertIsNotNone(self.s.open_record(self.doctor, 1001))

    def test_duplicate_requests_blocked(self):
        self.assertIsNotNone(self.s.request_access(self.doctor, 1001))
        self.assertIsNone(self.s.request_access(self.doctor, 1001))
        self.assertEqual(len(self.s.requests), 1)

    def test_only_the_patient_can_answer_and_only_once(self):
        req = self.s.request_access(self.doctor, 1001)
        self.assertFalse(self.s.respond_to_request(req.request_id, 9999, True))
        self.assertTrue(self.s.respond_to_request(req.request_id, 1001, True))
        self.assertFalse(self.s.respond_to_request(req.request_id, 1001, False))

    def test_denied_doctor_can_ask_again(self):
        req = self.s.request_access(self.doctor, 1001)
        self.s.respond_to_request(req.request_id, 1001, False)
        self.assertEqual(self.s.access_status(2001, 1001), "denied")
        self.assertIsNotNone(self.s.request_access(self.doctor, 1001))

    def test_revoke_locks_the_record_again(self):
        req = self.approve()
        self.assertTrue(self.s.revoke_access(req.request_id, 1001))
        self.assertEqual(self.s.access_status(2001, 1001), "revoked")
        self.assertIsNone(self.s.add_consultation(self.doctor, 1001, "after revoke"))
        self.assertFalse(self.s.revoke_access(req.request_id, 1001))  # already revoked

    def test_only_the_owner_can_revoke(self):
        req = self.approve()
        self.assertFalse(self.s.revoke_access(req.request_id, 9999))

    def test_emergency_opens_without_approval_and_is_logged(self):
        self.assertIsNotNone(self.s.emergency_access(self.doctor, 1001, "unconscious"))
        self.assertIsNotNone(self.s.open_record(self.doctor, 1001, emergency=True))
        self.assertEqual(self.s.record_views[-1].via, "emergency")
        self.assertEqual(len(self.s.emergency_logs), 1)


class Notifications(unittest.TestCase):
    def test_request_notifies_patient_and_answer_notifies_doctor(self):
        s = fresh_system()
        req = s.request_access(s.doctors[2001], 1001)
        self.assertEqual(s.unread_count(1001), 1)
        s.respond_to_request(req.request_id, 1001, True)
        self.assertEqual(s.unread_count(2001), 1)
        s.mark_inbox_read(1001)
        self.assertEqual(s.unread_count(1001), 0)


class Registration(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system()

    def test_bad_input_is_rejected_with_a_message(self):
        for args in [("", "x", "M", 20), ("A", "", "M", 20), ("A", "x", "M", "abc"), ("A", "x", "M", 500)]:
            with self.assertRaises(ValueError):
                self.s.register_patient(*args)
        for contact in ["123", "abcdefghij", "123456789012"]:
            with self.assertRaises(ValueError):
                self.s.register_patient("A", "x", "M", 20, contact_number=contact)
        with self.assertRaises(ValueError):
            self.s.register_patient("A", "x", "M", 20, blood_type="Z+")

    def test_good_input_gets_the_next_id_and_a_display_id(self):
        p = self.s.register_patient("Ana", "x", "F", 20, contact_number="0917 555 1234")
        self.assertEqual(p.user_id, 1002)
        self.assertEqual(p.contact_number, "09175551234")
        self.assertTrue(p.display_id.startswith("PT-") and p.display_id.endswith("-01002"))

    def test_parse_id(self):
        self.assertEqual(MedScanSystem.parse_id("1001"), 1001)
        self.assertEqual(MedScanSystem.parse_id("PT-2026-01001"), 1001)
        self.assertIsNone(MedScanSystem.parse_id("abc"))
        self.assertIsNone(MedScanSystem.parse_id(None))

    def test_editing_info_replaces_the_lists(self):
        self.s.update_patient_info(1001, "Peanuts", "", "Metformin", "A+", "09175551234")
        record = self.s.patients[1001].record
        self.assertEqual((record.allergies, record.surgeries, record.medications, record.blood_type),
                         (["Peanuts"], [], ["Metformin"], "A+"))


class ConsultationIds(unittest.TestCase):
    def test_numbering_continues_after_a_restart(self):
        path = os.path.join(tempfile.mkdtemp(), "t.pkl")
        store = PickleStore(path)
        s = MedScanSystem.load(store)
        doctor = s.doctors[2001]
        s.respond_to_request(s.request_access(doctor, 1001).request_id, 1001, True)
        self.assertEqual(s.add_consultation(doctor, 1001, "one").consultation_id, 1)
        s.save()
        again = MedScanSystem.load(PickleStore(path))
        self.assertEqual(again.add_consultation(again.doctors[2001], 1001, "two").consultation_id, 2)


class SystemLoad(unittest.TestCase):
    def test_empty_store_starts_with_the_demo_accounts(self):
        s = MedScanSystem.load(MemoryStore())
        self.assertEqual((list(s.doctors), list(s.patients)), ([2001], [1001]))
        self.assertTrue(s.authenticate(2001, "doc123") and s.authenticate(1001, "pat123"))
        self.assertIsNone(s.authenticate(1001, "wrong"))

    def test_console_demo_system_without_a_store_can_still_call_save(self):
        MedScanSystem().save()  # must do nothing and not crash


if __name__ == "__main__":
    unittest.main()
