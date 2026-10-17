"""Connecting to MySQL: the database is created when missing, old layouts are detected, errors are clear."""
import re
import unittest

import pymysql

from data.D_Database import SCHEMA_VERSION, SQL_DIR, Database, DatabaseError


class TemporaryDatabase(unittest.TestCase):
    """Base for tests that need a database that does not exist yet."""
    NAME = "db_medscan_scratch_tmp"

    def setUp(self):
        self.db = Database.from_environment(name=self.NAME)
        try:
            self.drop()
        except DatabaseError as error:
            self.fail(str(error))
        self.addCleanup(self.drop)

    def drop(self):
        conn = self.db._open(None)
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{self.NAME}`")
            conn.commit()
        finally:
            conn.close()

    def exists(self):
        conn = self.db._open(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s", (self.NAME,))
                return cur.fetchone() is not None
        finally:
            conn.close()


class AutoCreate(TemporaryDatabase):
    def test_a_missing_database_is_created_with_tables_test_accounts_and_utf8mb4(self):
        self.assertFalse(self.exists())
        self.db.prepare()
        self.assertTrue(self.exists())
        with self.db.cursor() as cur:
            cur.execute("SELECT (SELECT COUNT(*) FROM tb_doctors) AS d, (SELECT COUNT(*) FROM tb_patients) AS p")
            self.assertEqual(cur.fetchone(), {"d": 1, "p": 1})
            cur.execute("SELECT DEFAULT_CHARACTER_SET_NAME AS c FROM information_schema.SCHEMATA "
                        "WHERE SCHEMA_NAME = %s", (self.NAME,))
            self.assertEqual(cur.fetchone()["c"], "utf8mb4")


class OldLayouts(TemporaryDatabase):
    def test_tables_from_an_older_version_are_refused_with_the_fix_and_reset_rebuilds_them(self):
        with self.db.cursor() as cur:  # creates the database too
            cur.execute("CREATE TABLE patients (user_id INT PRIMARY KEY, age INT)")
        with self.assertRaises(DatabaseError) as caught:
            self.db.prepare()
        self.assertIn("older version", str(caught.exception))
        self.assertIn("reset_database.py", str(caught.exception))
        self.db.reset()
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s "
                        "AND TABLE_NAME = 'tb_patients' AND COLUMN_NAME = 'date_of_birth'", (self.NAME,))
            self.assertEqual(cur.fetchone()["n"], 1)


class FreshStart(TemporaryDatabase):
    """Old layouts are not upgraded: a reset removes them, and the new tables take their place."""

    def table_names(self):
        with self.db.cursor() as cur:
            cur.execute("SELECT TABLE_NAME AS name FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s", (self.NAME,))
            return sorted(row["name"] for row in cur.fetchall())

    def test_a_reset_leaves_no_old_tables_behind(self):
        with self.db.cursor() as cur:  # creates the database too
            cur.execute("CREATE TABLE patients (user_id INT PRIMARY KEY)")
            cur.execute("CREATE TABLE schema_version (version INT)")
        self.db.reset()
        names = self.table_names()
        self.assertTrue(all(name.startswith("tb_") for name in names), names)
        self.assertEqual(len(names), 11)

    def test_every_table_and_every_key_follows_the_naming_rules(self):
        self.db.prepare()
        with self.db.cursor() as cur:
            cur.execute("SELECT TABLE_NAME AS t, COLUMN_NAME AS c, COLUMN_KEY AS k FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s", (self.NAME,))
            columns = cur.fetchall()
            cur.execute("SELECT DISTINCT INDEX_NAME AS name FROM information_schema.STATISTICS "
                        "WHERE TABLE_SCHEMA = %s AND INDEX_NAME <> 'PRIMARY'", (self.NAME,))
            indexes = [row["name"] for row in cur.fetchall()]
        for row in columns:
            self.assertTrue(row["t"].startswith("tb_"), row)
            if row["k"] == "PRI" and row["t"] != "tb_schema_version":
                self.assertTrue(row["c"].endswith("_id"), row)              # every primary key is <thing>_id
            self.assertNotEqual(row["c"], "user_id")                         # patients and doctors have their own key names
        # ix_ for indexes, uq_ for unique keys, and fk_ (MySQL names a link's own index after the link)
        self.assertTrue(all(name.split("_")[0] in ("ix", "uq", "fk") for name in indexes), indexes)


class DemoData(TemporaryDatabase):
    """database/demo_data.sql: optional sample data that makes the screens look lived-in."""

    def test_it_is_added_once_and_only_once(self):
        self.db.prepare()
        self.assertTrue(self.db.add_demo_data())
        self.assertFalse(self.db.add_demo_data())                            # already there: nothing is added again
        with self.db.cursor() as cur:
            cur.execute("SELECT (SELECT COUNT(*) FROM tb_doctors) AS d, (SELECT COUNT(*) FROM tb_patients) AS p")
            self.assertEqual(cur.fetchone(), {"d": 4, "p": 5})               # the demo accounts plus 3 doctors and 4 patients

    def test_it_gives_every_kind_of_situation_the_screens_show(self):
        self.db.prepare()
        self.db.add_demo_data()
        with self.db.cursor() as cur:
            cur.execute("SELECT status, via, COUNT(*) AS n FROM tb_access_requests GROUP BY status, via")
            found = {(row["status"], row["via"]): row["n"] for row in cur.fetchall()}
            cur.execute("SELECT (SELECT COUNT(*) FROM tb_qr_scans) AS scans, (SELECT COUNT(*) FROM tb_emergency_logs) AS emergencies, "
                        "(SELECT COUNT(*) FROM tb_notifications WHERE is_read = 0) AS unread")
            counts = cur.fetchone()
        self.assertIn(("Approved", "qr"), found)
        self.assertIn(("Approved", "request"), found)
        self.assertIn(("Pending", "request"), found)
        self.assertIn(("Denied", "request"), found)
        self.assertGreaterEqual(counts["scans"], 1)
        self.assertGreaterEqual(counts["emergencies"], 2)
        self.assertGreaterEqual(counts["unread"], 1)

    def test_the_rules_see_the_sample_data_the_way_the_screens_expect(self):
        from logic.L_MedScan_System import MedScanSystem
        self.db.prepare()
        self.db.add_demo_data()
        system = MedScanSystem(self.db)
        self.assertEqual(system.access_status(2001, 1001), "approved")       # Reyes got in by scanning Juan's code
        self.assertEqual(len(system.doctor_groups_for_patient(1001)["waiting"]), 1)   # Dr. Santos waits for Juan's answer
        self.assertEqual(len(system.doctor_groups_for_patient(1001)["with_access"]), 2)
        self.assertEqual(len(system.get_patient(1001).record.consultations), 2)
        ana = system.resolve_login("0917 111 0001")
        self.assertIsNotNone(system.authenticate(ana, "demo123"))            # the sample accounts can log in

    def test_the_reset_script_takes_a_demo_option(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parent.parent / "reset_database.py").read_text(encoding="utf-8")
        self.assertIn("--demo", script)
        self.assertIn("add_demo_data", script)


class ConnectionErrors(unittest.TestCase):
    def test_a_database_that_cannot_be_reached_says_connection_error(self):
        unreachable = Database(port=3999)  # nothing listens here
        with self.assertRaises(DatabaseError) as caught:
            unreachable.prepare()
        message = str(caught.exception)
        self.assertTrue(message.startswith("Connection error"))
        self.assertIn("3999", message)
        self.assertNotIn("XAMPP", message)

    def test_a_wrong_password_is_also_a_connection_error(self):
        db = Database.from_environment()
        db.password = "definitely-not-the-password"
        try:
            db.prepare()
        except DatabaseError as error:
            self.assertTrue(str(error).startswith("Connection error"))
        # (an XAMPP root with no password also accepts any password, in which case there is nothing to refuse)

    def test_a_database_name_must_be_plain(self):
        for bad in ["bad name", "x`; DROP DATABASE y; --", "", "a-b"]:
            with self.assertRaises(ValueError, msg=bad):
                Database(name=bad)


class SqlFiles(unittest.TestCase):
    def test_the_schema_version_in_python_matches_schema_sql(self):
        with open(f"{SQL_DIR}/schema.sql", encoding="utf-8") as f:
            found = re.search(r"INSERT IGNORE INTO tb_schema_version \(version\) VALUES \((\d+)\)", f.read())
        self.assertEqual(int(found.group(1)), SCHEMA_VERSION)

    def test_every_statement_in_the_sql_files_is_found(self):
        self.assertEqual(len(Database._statements("schema.sql")), 12)  # tb_schema_version, 10 tables, the version row
        self.assertEqual(len(Database._statements("seed.sql")), 3)
        for name in ("schema.sql", "seed.sql", "demo_data.sql"):
            for statement in Database._statements(name):
                self.assertNotIn("--", statement)

    def test_all_tables_in_schema_sql_are_in_the_tables_list(self):
        from data.D_Database import TABLES
        with open(f"{SQL_DIR}/schema.sql", encoding="utf-8") as f:
            created = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", f.read())
        self.assertEqual(sorted(created), sorted(TABLES))


if __name__ == "__main__":
    unittest.main()
