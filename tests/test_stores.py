"""Round-trip tests: whatever a store saves, it must load back exactly.
The MySQL tests use the separate database db_medscan_test and are skipped if MySQL is not running."""
import os
import tempfile
import unittest

from data.D_Pickle_Store import PickleStore
from logic.L_MedScan_System import MedScanSystem
from tests.helpers import build_sample_system, snapshot


class StoreContract:
    """Tests every store must pass. Subclasses provide self.store (a fresh, empty store)."""

    def test_empty_store_loads_nothing(self):
        self.assertIsNone(self.store.load())

    def test_round_trip_keeps_everything(self):
        original = build_sample_system()
        self.store.save(original)
        loaded = self.store.load()
        self.assertEqual(snapshot(loaded), snapshot(original))

    def test_passwords_survive(self):
        self.store.save(build_sample_system())
        loaded = self.store.load()
        self.assertTrue(loaded.authenticate(2001, "doc123"))
        self.assertTrue(loaded.authenticate(1002, "ana123"))
        self.assertIsNone(loaded.authenticate(1002, "wrong"))

    def test_new_ids_continue_after_loading(self):
        self.store.save(build_sample_system())
        loaded = self.store.load()
        self.assertEqual(loaded.register_patient("New", "x", "M", 30).user_id, 1003)
        self.assertEqual(loaded.register_doctor("New", "x", "ENT").user_id, 2003)

    def test_saving_again_replaces_the_old_data(self):
        self.store.save(build_sample_system())
        self.store.save(MedScanSystem.load(self.empty_store()))
        loaded = self.store.load()
        self.assertEqual(list(loaded.patients), [1001])
        self.assertEqual(loaded.requests, [])

    def test_system_load_creates_and_then_reuses_the_demo_data(self):
        first = MedScanSystem.load(self.store)
        first.register_patient("Extra", "x", "F", 40)
        first.save()
        second = MedScanSystem.load(self.store)
        self.assertEqual(sorted(second.patients), [1001, 1002])

    @staticmethod
    def empty_store():
        from data.D_Memory_Store import MemoryStore
        return MemoryStore()


class PickleStoreTests(StoreContract, unittest.TestCase):
    def setUp(self):
        self.store = PickleStore(os.path.join(tempfile.mkdtemp(), "test.pkl"))

    def test_pickle_file_holds_data_only_not_the_store(self):
        system = MedScanSystem.load(self.store)
        self.assertNotIn("_store", system.__getstate__())


class MySQLStoreTests(StoreContract, unittest.TestCase):
    def setUp(self):
        try:
            from data.D_MySQL_Store import MySQLStore
            self.store = MySQLStore(database="db_medscan_test")
            self.store.check()
        except Exception as error:
            self.skipTest(f"MySQL not available: {error}")
        self.wipe()

    def tearDown(self):
        if hasattr(self, "store"):
            try:
                self.wipe()
            except Exception:
                pass

    def wipe(self):
        """Empty every table by saving a system with nothing in it."""
        self.store.save(MedScanSystem())

    def test_tables_exist_with_foreign_keys(self):
        conn = self.store._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                tables = {row[0] for row in cur.fetchall()}
                cur.execute("SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS "
                            "WHERE CONSTRAINT_SCHEMA = %s", (self.store.database,))
                foreign_keys = cur.fetchone()[0]
        finally:
            conn.close()
        self.assertTrue({"patients", "doctors", "record_items", "consultations", "access_requests",
                         "emergency_logs", "record_views", "notifications"} <= tables)
        self.assertEqual(foreign_keys, 9)

    def test_a_failed_save_changes_nothing(self):
        self.store.save(build_sample_system())
        before = snapshot(self.store.load())
        broken = build_sample_system()
        broken.requests[0].doctor_id = 99999  # a doctor that does not exist: the foreign key must refuse it
        with self.assertRaises(Exception):
            self.store.save(broken)
        self.assertEqual(snapshot(self.store.load()), before)


if __name__ == "__main__":
    unittest.main()
