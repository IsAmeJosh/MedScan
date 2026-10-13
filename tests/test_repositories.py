"""The database side: data really lands in MySQL, a second system sees it, transactions behave,
the constraints refuse bad data, and several users at once cannot break the rules.
These tests use real commits (committed_system), so each one resets the test database."""
import threading
import unittest
from unittest import mock

import pymysql

from logic.L_MedScan_System import MedScanSystem
from django.test import Client

from data.D_Database import Database
from gui import G_Views
from tests.helpers import (PASSWORD, build_sample_data, committed_system, count, fresh_system, login,
                           rows)
from tests.helpers import new_patient


class Persistence(unittest.TestCase):
    """The sample data is saved once (really committed) and every test only reads it, from a second system."""

    @classmethod
    def setUpClass(cls):
        cls.s = G_Views.system
        G_Views.db.prepare()
        G_Views.db.reset_data()
        cls.santos, cls.ana = build_sample_data(cls.s)
        cls.other = MedScanSystem(cls.s.db)  # a second system: shares nothing in memory, only the database

    @classmethod
    def tearDownClass(cls):
        G_Views.db.reset_data()

    def test_every_table_received_rows(self):
        expected = {"doctors": 2, "patients": 2, "record_items": 5, "consultations": 2, "access_requests": 3,
                    "emergency_logs": 1, "record_views": 1}
        for table, n in expected.items():
            self.assertEqual(count(table), n, table)
        self.assertGreaterEqual(count("notifications"), 5)

    def test_a_second_system_reads_the_same_patient_back(self):
        ana = self.other.get_patient(self.ana.user_id)
        self.assertEqual((ana.name, ana.sex, ana.contact_number, ana.record.blood_type),
                         ("Ana Lopez", "Female", "09281112222", "A+"))
        self.assertEqual((ana.record.allergies, ana.record.surgeries, ana.record.medications),
                         (["Latex", "Dust"], [], ["Cetirizine"]))
        self.assertEqual(ana.display_id[:3], "PT-")

    def test_consultations_come_back_with_their_text_and_order(self):
        juan = self.other.get_patient(1001)
        self.assertEqual([c.notes for c in juan.record.consultations],
                         ["Headache for 3 days. Rest advised. Café intake reduced.", "Follow-up: resolved."])
        self.assertEqual({c.doctor_name for c in juan.record.consultations}, {"Reyes"})

    def test_statuses_logs_and_notifications_are_saved(self):
        self.assertEqual(self.other.access_status(2001, 1001), "revoked")
        self.assertEqual(self.other.access_status(self.santos.user_id, 1001), "denied")
        self.assertEqual(self.other.access_status(self.santos.user_id, self.ana.user_id), "pending")
        (log, doctor), = self.other.emergency_rows_for_patient(1001)
        self.assertEqual((log.reason, doctor.name), ("Patient unconscious on arrival", "Antonio Santos"))
        self.assertEqual(self.other.unread_count(1001), 0)  # the sample data ends with the patient reading the inbox
        self.assertTrue(all(n.is_read for n in self.other.inbox(1001)))
        self.assertFalse(all(n.is_read for n in self.other.inbox(2001)))  # the doctor has not read theirs

    def test_passwords_survive_and_login_works(self):
        self.assertTrue(self.other.authenticate(2001, "doc123"))
        self.assertTrue(self.other.authenticate(self.ana.user_id, "ana123"))
        self.assertIsNone(self.other.authenticate(self.ana.user_id, "wrong"))

    def test_a_light_patient_has_no_record_but_a_full_one_does(self):
        light = self.other._patients.get_many([1001, self.ana.user_id], with_record=False)
        full = self.other._patients.get_many([1001, self.ana.user_id])
        self.assertEqual(light[1001].name, "Juan Dela Cruz")
        self.assertEqual(light[1001].record.allergies, [])
        self.assertEqual(light[1001].record.blood_type, "O+")  # cheap to include, so the lists still show it
        self.assertEqual(full[1001].record.allergies, ["Penicillin"])
        self.assertEqual(len(full[1001].record.consultations), 2)


class NewIds(unittest.TestCase):
    def test_new_ids_continue_after_the_saved_ones(self):
        s = fresh_system(self)
        santos, ana = build_sample_data(s)
        later = MedScanSystem(s.db)
        self.assertGreater(new_patient(later, "New", PASSWORD, "M", "1990-01-01").user_id, ana.user_id)
        self.assertGreater(later.register_doctor("New", PASSWORD, "ENT").user_id, santos.user_id)


class Transactions(unittest.TestCase):
    """These tests check real commits and rollbacks, so they cannot run inside the rolled-back test transaction.
    They clean up the few rows they create."""

    @classmethod
    def setUpClass(cls):
        cls.s = G_Views.system
        cls.db = cls.s.db
        G_Views.db.prepare()
        G_Views.db.reset_data()

    def tearDown(self):
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM record_items WHERE item IN ('Latex', 'Dust')")
            cur.execute("DELETE FROM patients WHERE user_id > 1001")
            cur.execute("DELETE FROM doctors WHERE user_id > 2001")

    @classmethod
    def tearDownClass(cls):
        G_Views.db.reset_data()

    def insert_doctor(self, name):
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO doctors (name, password, specialty, created_year) VALUES (%s, 'x', 'y', 2026)",
                        (name,))

    def test_an_error_inside_a_unit_of_work_undoes_all_of_it(self):
        with self.assertRaises(RuntimeError):
            with self.db.unit_of_work():
                self.insert_doctor("Ghost 1")
                self.insert_doctor("Ghost 2")
                raise RuntimeError("boom")
        self.assertEqual(count("doctors", "name LIKE 'Ghost%'"), 0)

    def test_a_unit_of_work_inside_another_joins_it(self):
        with self.assertRaises(RuntimeError):
            with self.db.unit_of_work():
                with self.db.unit_of_work():
                    self.insert_doctor("Ghost")
                raise RuntimeError("the outer block fails after the inner one finished")
        self.assertEqual(count("doctors", "name = 'Ghost'"), 0)

    def test_a_good_unit_of_work_is_saved(self):
        with self.db.unit_of_work():
            self.insert_doctor("Kept")
        self.assertEqual(count("doctors", "name = 'Kept'"), 1)

    def test_a_refused_registration_leaves_no_rows_behind(self):
        before = count("patients")
        with self.assertRaises(ValueError):
            new_patient(self.s, "Ana", PASSWORD, "F", "1990-01-01", contact_number="bad")
        self.assertEqual(count("patients"), before)

    def test_adding_a_patient_and_their_items_is_all_or_nothing(self):
        before = (count("patients"), count("record_items"))
        with self.assertRaises(pymysql.MySQLError):
            new_patient(self.s, "Ana", PASSWORD, "F", "1990-01-01", allergies="Latex")
            with self.db.unit_of_work():
                new_patient(self.s, "Bea", PASSWORD, "F", "1990-01-01", allergies="Dust")
                with self.db.cursor() as cur:
                    cur.execute("INSERT INTO record_items (patient_id, kind, item) VALUES (999999, 'allergy', 'x')")
        self.assertEqual(count("patients"), before[0] + 1)      # Ana was saved on her own
        self.assertEqual(count("patients", "name = 'Bea'"), 0)  # Bea was rolled back with her failed item


class Constraints(unittest.TestCase):
    """The database itself refuses bad data, even if the application code had a bug.
    (A refused statement leaves the surrounding test transaction intact, so these can run inside it.)"""

    def setUp(self):
        self.s = fresh_system(self)
        self.db = self.s.db

    def refuses(self, sql, *params):
        with self.assertRaises(pymysql.MySQLError):
            with self.db.cursor() as cur:
                cur.execute(sql, params)

    def test_foreign_keys_refuse_orphans(self):
        self.refuses("INSERT INTO access_requests (doctor_id, patient_id) VALUES (999, 1001)")
        self.refuses("INSERT INTO access_requests (doctor_id, patient_id) VALUES (2001, 999)")
        self.refuses("INSERT INTO consultations (patient_id, doctor_id, doctor_name, notes) VALUES (1001, 999, 'x', 'y')")
        self.refuses("INSERT INTO emergency_logs (doctor_id, patient_id, reason) VALUES (2001, 999, 'x')")
        self.refuses("INSERT INTO record_views (doctor_id, patient_id, via) VALUES (999, 1001, 'approved')")

    def test_a_patient_with_history_cannot_be_deleted_by_accident(self):
        build_sample_data(self.s)
        self.refuses("DELETE FROM patients WHERE user_id = 1001")

    def test_status_and_via_only_take_known_values(self):
        self.refuses("INSERT INTO access_requests (doctor_id, patient_id, status) VALUES (2001, 1001, 'Maybe')")
        self.refuses("INSERT INTO record_views (doctor_id, patient_id, via) VALUES (2001, 1001, 'sneaked')")

    def test_mobile_number_and_blood_type_are_checked(self):
        base = ("INSERT INTO patients (name, password, sex, date_of_birth, created_year, {col}) "
                "VALUES ('Z', 'secret1', 'F', '1990-01-01', 2026, %s)")
        self.refuses(base.format(col="contact_number"), "12345")
        self.refuses(base.format(col="contact_number"), "")
        self.refuses(base.format(col="blood_type"), "Z+")   # (no mobile number either: also refused)
        with self.db.cursor() as cur:
            cur.execute(base.format(col="contact_number"), ("09170000001",))  # a valid, unused one goes through

    def test_one_mobile_number_cannot_belong_to_two_patients(self):
        insert = ("INSERT INTO patients (name, password, sex, date_of_birth, contact_number, created_year) "
                  "VALUES ('Copy', 'secret1', 'F', '1990-01-01', %s, 2026)")
        self.refuses(insert, "09171234567")   # Juan's number

    def test_missing_required_values_are_refused(self):
        self.refuses("INSERT INTO patients (name, password, sex, created_year) VALUES ('Z', 'secret1', 'F', 2026)")


class SeedAndSchema(unittest.TestCase):
    def test_the_test_accounts_come_from_seed_sql(self):
        committed_system(self)
        (doctor,) = rows("SELECT * FROM doctors")
        (patient,) = rows("SELECT * FROM patients")
        self.assertEqual((doctor["user_id"], doctor["name"], doctor["password"], doctor["clinic"]),
                         (2001, "Reyes", "doc123", "Bayanihan Family Clinic"))
        self.assertEqual((patient["user_id"], patient["name"], patient["password"], patient["blood_type"]),
                         (1001, "Juan Dela Cruz", "pat123", "O+"))
        self.assertEqual([r["item"] for r in rows("SELECT item FROM record_items ORDER BY item_id")],
                         ["Penicillin", "Appendectomy"])

    def test_prepare_can_run_again_without_duplicating_anything(self):
        s = committed_system(self)
        s.db.prepare()
        s.db.prepare()
        self.assertEqual((count("doctors"), count("patients"), count("record_items")), (1, 1, 2))

    def test_reset_data_goes_back_to_the_test_accounts_and_numbers(self):
        s = committed_system(self)
        build_sample_data(s)
        s.db.reset_data()
        self.assertEqual((count("doctors"), count("patients"), count("access_requests"), count("notifications")),
                         (1, 1, 0, 0))
        self.assertEqual(new_patient(s, "Next", PASSWORD, "F", "1990-01-01").user_id, 1002)
        self.assertEqual(s.register_doctor("Next", PASSWORD, "ENT").user_id, 2002)

    def test_ids_are_handed_out_by_the_database_and_never_reused(self):
        s = committed_system(self)
        first = new_patient(s, "One", PASSWORD, "F", "1990-01-01").user_id
        second = new_patient(s, "Two", PASSWORD, "F", "1990-01-01").user_id
        self.assertEqual(second, first + 1)


class SeveralUsersAtOnce(unittest.TestCase):
    def test_simultaneous_requests_from_one_doctor_make_one_request(self):
        s = committed_system(self)
        doctor = s.get_doctor(2001)
        results = []

        def ask():
            results.append(s.request_access(doctor, 1001))

        threads = [threading.Thread(target=ask) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(count("access_requests"), 1)
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(count("notifications", "recipient_id = 1001"), 1)

    def test_simultaneous_answers_are_counted_once(self):
        s = committed_system(self)
        request = s.request_access(s.get_doctor(2001), 1001)
        results = []

        def answer(approve):
            results.append(s.respond_to_request(request.request_id, 1001, approve))

        threads = [threading.Thread(target=answer, args=(i % 2 == 0,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(results), 1)
        self.assertEqual(count("notifications", "recipient_id = 2001"), 1)


class RequestTransactions(unittest.TestCase):
    """What the website does with the database for one page. These requests really commit, because no test
    transaction is open around them."""

    @classmethod
    def setUpClass(cls):
        G_Views.db.prepare()
        G_Views.db.reset_data()

    @classmethod
    def tearDownClass(cls):
        G_Views.db.reset_data()

    def tearDown(self):
        with G_Views.db.cursor() as cur:
            cur.execute("DELETE FROM notifications")
            cur.execute("DELETE FROM access_requests")

    def count_connections(self, work):
        """Run work() and return how many database connections were opened meanwhile."""
        opened = []
        original = Database.connect

        def counting(db):
            opened.append(1)
            return original(db)

        with mock.patch.object(Database, "connect", counting):
            work()
        return len(opened)

    def test_a_page_that_works_is_saved_for_everyone_to_see(self):
        login(2001, "doc123").post("/request/1001/")
        self.assertEqual(count("access_requests"), 1)   # read back on a different connection
        self.assertEqual(count("notifications", "recipient_id = 1001"), 1)

    def test_a_page_that_fails_saves_nothing_it_started(self):
        doctor = login(2001, "doc123")
        with mock.patch("gui.G_Views.messages.success", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                doctor.post("/request/1001/")   # the request is written first, then the page breaks
        self.assertEqual(count("access_requests"), 0)
        self.assertEqual(count("notifications"), 0)

    def test_a_whole_page_uses_one_connection(self):
        patient = login(1001, "pat123")
        self.assertEqual(self.count_connections(lambda: patient.get("/dashboard/")), 1)
        self.assertEqual(self.count_connections(lambda: patient.get("/privacy/")), 1)
        self.assertEqual(self.count_connections(lambda: patient.get("/record/")), 1)
        doctor = login(2001, "doc123")
        self.assertEqual(self.count_connections(lambda: doctor.get("/dashboard/")), 1)
        self.assertEqual(self.count_connections(lambda: doctor.get("/patients/")), 1)

    def test_a_page_that_asks_the_database_nothing_opens_no_connection(self):
        self.assertEqual(self.count_connections(lambda: Client().get("/")), 0)
        self.assertEqual(self.count_connections(lambda: Client().get("/register/")), 0)

    def test_the_connection_is_closed_after_the_page(self):
        login(1001, "pat123").get("/dashboard/")
        self.assertFalse(G_Views.db.in_transaction)


if __name__ == "__main__":
    unittest.main()
