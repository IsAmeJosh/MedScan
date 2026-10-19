"""The rules inside MedScanSystem: access, emergencies, the view log, notifications, registration."""
import unittest
from datetime import date

from logic.L_MedScan_System import MedScanSystem
from models.M_Notification import Notification
from tests.helpers import (BORN, PASSWORD, age_emergencies, age_views, approve, count, fresh_system, rows)
from tests.helpers import new_patient


class AccessRules(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doctor = self.s.get_doctor(2001)

    def test_no_access_before_approval(self):
        self.assertEqual(self.s.access_status(2001, 1001), "none")
        self.assertIsNone(self.s.add_consultation(self.doctor, 1001, "too early"))
        self.assertIsNone(self.s.open_record(self.doctor, 1001))
        self.assertEqual(count("tb_record_views"), 0)

    def test_approval_allows_notes_and_viewing(self):
        approve(self.s)
        self.assertEqual(self.s.access_status(2001, 1001), "approved")
        self.assertIsNotNone(self.s.add_consultation(self.doctor, 1001, "fever"))
        self.assertIsNotNone(self.s.open_record(self.doctor, 1001))

    def test_duplicate_requests_blocked(self):
        self.assertIsNotNone(self.s.request_access(self.doctor, 1001))
        self.assertIsNone(self.s.request_access(self.doctor, 1001))
        self.assertEqual(count("tb_access_requests"), 1)

    def test_a_request_for_nobody_is_refused(self):
        self.assertIsNone(self.s.request_access(self.doctor, 9999))
        self.assertEqual(count("tb_access_requests"), 0)

    def test_only_the_patient_can_answer_and_only_once(self):
        req = self.s.request_access(self.doctor, 1001)
        self.assertFalse(self.s.respond_to_request(req.request_id, 9999, True))
        self.assertTrue(self.s.respond_to_request(req.request_id, 1001, True))
        self.assertFalse(self.s.respond_to_request(req.request_id, 1001, False))
        self.assertFalse(self.s.respond_to_request(12345, 1001, True))

    def test_denied_doctor_can_ask_again(self):
        req = self.s.request_access(self.doctor, 1001)
        self.s.respond_to_request(req.request_id, 1001, False)
        self.assertEqual(self.s.access_status(2001, 1001), "denied")
        self.assertIsNotNone(self.s.request_access(self.doctor, 1001))
        self.assertEqual(self.s.access_status(2001, 1001), "pending")

    def test_revoke_locks_the_record_again(self):
        req = approve(self.s)
        self.assertTrue(self.s.revoke_access(req.request_id, 1001))
        self.assertEqual(self.s.access_status(2001, 1001), "revoked")
        self.assertIsNone(self.s.add_consultation(self.doctor, 1001, "after revoke"))
        self.assertFalse(self.s.revoke_access(req.request_id, 1001))  # already revoked
        self.assertIsNotNone(self.s.request_access(self.doctor, 1001))  # may ask again

    def test_only_the_owner_can_revoke_and_only_an_approved_request(self):
        req = approve(self.s)
        self.assertFalse(self.s.revoke_access(req.request_id, 9999))
        pending = self.s.request_access(self.s.register_doctor("Cruz", PASSWORD, "ENT"), 1001)
        self.assertFalse(self.s.revoke_access(pending.request_id, 1001))


class EmergencyAccess(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doctor = self.s.get_doctor(2001)

    def test_opens_without_approval_and_is_logged(self):
        self.assertIsNotNone(self.s.emergency_access(self.doctor, 1001, "unconscious"))
        self.assertTrue(self.s.can_view_record(2001, 1001))
        self.assertIsNotNone(self.s.open_record(self.doctor, 1001))
        self.assertEqual(rows("SELECT via FROM tb_record_views")[0]["via"], "emergency")
        self.assertEqual(count("tb_emergency_logs"), 1)

    def test_lets_the_doctor_write_notes_too(self):
        self.s.emergency_access(self.doctor, 1001, "unconscious")
        self.assertIsNotNone(self.s.add_consultation(self.doctor, 1001, "ER note"))

    def test_lasts_an_hour_and_then_expires(self):
        self.s.emergency_access(self.doctor, 1001, "unconscious")
        age_emergencies(59)
        self.assertTrue(self.s.can_view_record(2001, 1001))
        age_emergencies(2)  # now 61 minutes old
        self.assertFalse(self.s.can_view_record(2001, 1001))
        self.assertIsNone(self.s.open_record(self.doctor, 1001))
        self.assertIsNone(self.s.add_consultation(self.doctor, 1001, "too late"))

    def test_only_covers_the_one_patient_and_the_one_doctor(self):
        other_patient = new_patient(self.s, "Eve", PASSWORD, "F", BORN)
        other_doctor = self.s.register_doctor("Cruz", PASSWORD, "ENT")
        self.s.emergency_access(self.doctor, 1001, "unconscious")
        self.assertFalse(self.s.can_view_record(2001, other_patient.user_id))
        self.assertFalse(self.s.can_view_record(other_doctor.user_id, 1001))

    def test_unknown_patient_and_missing_reason(self):
        self.assertIsNone(self.s.emergency_access(self.doctor, 9999, "x"))
        self.assertEqual(count("tb_emergency_logs"), 0)

    def test_the_patient_is_notified(self):
        self.s.emergency_access(self.doctor, 1001, "Collapsed")
        self.assertTrue(any("emergency: Collapsed" in n.message for n in self.s.inbox(1001)))


class RecordViewLog(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doctor = self.s.get_doctor(2001)
        approve(self.s)

    def test_reopening_within_ten_minutes_is_logged_once(self):
        for _ in range(3):
            self.s.open_record(self.doctor, 1001)
        self.assertEqual(count("tb_record_views"), 1)

    def test_opening_after_the_quiet_time_is_logged_again(self):
        self.s.open_record(self.doctor, 1001)
        age_views(9)
        self.s.open_record(self.doctor, 1001)
        self.assertEqual(count("tb_record_views"), 1)
        age_views(2)
        self.s.open_record(self.doctor, 1001)
        self.assertEqual(count("tb_record_views"), 2)

    def test_another_doctor_is_logged_separately(self):
        other = self.s.register_doctor("Cruz", PASSWORD, "ENT")
        self.s.emergency_access(other, 1001, "unconscious")
        self.s.open_record(self.doctor, 1001)
        self.s.open_record(other, 1001)
        self.assertEqual(count("tb_record_views"), 2)

    def test_the_patient_can_list_who_looked(self):
        self.s.open_record(self.doctor, 1001)
        (view, doctor), = self.s.view_rows_for_patient(1001)
        self.assertEqual((doctor.name, view.via), ("Reyes", "approved"))


class Notifications(unittest.TestCase):
    def test_request_notifies_patient_and_answer_notifies_doctor(self):
        s = fresh_system(self)
        req = s.request_access(s.get_doctor(2001), 1001)
        self.assertEqual(s.unread_count(1001), 1)
        s.respond_to_request(req.request_id, 1001, True)
        self.assertEqual(s.unread_count(2001), 1)
        self.assertIn("Juan Dela Cruz approved", s.inbox(2001)[0].message)
        s.mark_inbox_read(1001)
        self.assertEqual(s.unread_count(1001), 0)
        self.assertEqual(s.unread_count(2001), 1)  # only that user's inbox changed

    def test_inbox_is_newest_first_and_can_be_limited(self):
        s = fresh_system(self)
        doctor = s.get_doctor(2001)
        s.request_access(doctor, 1001)
        s.emergency_access(doctor, 1001, "first")
        s.emergency_access(doctor, 1001, "second")
        self.assertIn("second", s.inbox(1001)[0].message)
        self.assertEqual(len(s.inbox(1001, limit=2)), 2)


class Registration(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_ids_come_from_the_database_and_display_ids_are_readable(self):
        p = new_patient(self.s, "Ana", PASSWORD, "F", BORN, contact_number="0917 555 1234")
        d = self.s.register_doctor("Cruz", PASSWORD, "ENT", "Rizal Clinic")
        self.assertGreater(p.user_id, 1001)
        self.assertGreater(d.user_id, 2001)
        self.assertTrue(p.display_id.startswith("PT-") and p.display_id.endswith(f"-{p.user_id:05d}"))
        self.assertTrue(d.display_id.startswith("DR-") and d.display_id.endswith(f"-{d.user_id:05d}"))
        self.assertEqual(p.contact_number, "09175551234")
        self.assertEqual(d.clinic, "Rizal Clinic")

    def test_age_is_worked_out_from_the_date_of_birth(self):
        today = date.today()
        birthday_passed = (today.month, today.day) >= (3, 14)
        p = new_patient(self.s, "Ana", PASSWORD, "F", date(today.year - 30, 3, 14))
        self.assertEqual(p.age, 30 if birthday_passed else 29)
        also = new_patient(self.s, "Bea", PASSWORD, "F", f"{today.year - 30}-03-14")  # text works too
        self.assertEqual(also.age, p.age)

    def test_parse_id(self):
        self.assertEqual(MedScanSystem.parse_id("1001"), 1001)
        self.assertEqual(MedScanSystem.parse_id("PT-2026-01001"), 1001)
        self.assertIsNone(MedScanSystem.parse_id("abc"))
        self.assertIsNone(MedScanSystem.parse_id(None))

    def test_editing_info_replaces_the_lists(self):
        self.s.update_patient_info(1001, "Peanuts", "", "Metformin", "A+", "09175551234")
        record = self.s.get_patient(1001).record
        self.assertEqual((record.allergies, record.surgeries, record.medications, record.blood_type),
                         (["Peanuts"], [], ["Metformin"], "A+"))
        self.assertEqual([i.added_by_role for i in record.allergies + record.medications], ["patient", "patient"])

    def test_authenticate(self):
        self.assertEqual(self.s.authenticate(2001, "doc123").name, "Reyes")
        self.assertEqual(self.s.authenticate(1001, "pat123").name, "Juan Dela Cruz")
        self.assertIsNone(self.s.authenticate(1001, "wrong"))
        self.assertIsNone(self.s.authenticate(None, "x"))
        self.assertIsNone(self.s.authenticate(555, "x"))


class Consultations(unittest.TestCase):
    def test_ids_keep_counting_up(self):
        s = fresh_system(self)
        doctor = s.get_doctor(2001)
        approve(s)
        first = s.add_consultation(doctor, 1001, "one")
        second = s.add_consultation(doctor, 1001, "two")
        self.assertEqual(second.consultation_id, first.consultation_id + 1)
        again = MedScanSystem(s.db).add_consultation(doctor, 1001, "three")  # a "restarted" system
        self.assertEqual(again.consultation_id, second.consultation_id + 1)

    def test_notes_are_saved_in_the_record(self):
        s = fresh_system(self)
        approve(s)
        s.add_consultation(s.get_doctor(2001), 1001, "  Mild fever  ")
        (note,) = s.get_patient(1001).record.consultations
        self.assertEqual((note.notes, note.doctor_name), ("Mild fever", "Reyes"))

    def test_blank_notes_are_refused(self):
        s = fresh_system(self)
        approve(s)
        self.assertIsNone(s.add_consultation(s.get_doctor(2001), 1001, "   "))
        self.assertEqual(count("tb_consultations"), 0)


class DoctorNumbers(unittest.TestCase):
    def test_a_doctors_patients_are_those_who_approved_them(self):
        s = fresh_system(self)
        doctor = s.get_doctor(2001)
        req = approve(s)
        s.add_consultation(doctor, 1001, "Checkup")
        self.assertEqual([p.name for p in s.patients_for_doctor(2001)], ["Juan Dela Cruz"])
        s.revoke_access(req.request_id, 1001)
        self.assertEqual(s.patients_for_doctor(2001), [])


if __name__ == "__main__":
    unittest.main()
