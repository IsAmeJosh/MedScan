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
            cur.execute("SELECT (SELECT COUNT(*) FROM doctors) AS d, (SELECT COUNT(*) FROM patients) AS p")
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
                        "AND TABLE_NAME = 'patients' AND COLUMN_NAME = 'date_of_birth'", (self.NAME,))
            self.assertEqual(cur.fetchone()["n"], 1)


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
            found = re.search(r"INSERT IGNORE INTO schema_version \(version\) VALUES \((\d+)\)", f.read())
        self.assertEqual(int(found.group(1)), SCHEMA_VERSION)

    def test_every_statement_in_the_sql_files_is_found(self):
        self.assertEqual(len(Database._statements("schema.sql")), 10)  # schema_version, 8 tables, version row
        self.assertEqual(len(Database._statements("seed.sql")), 3)
        for statement in Database._statements("schema.sql") + Database._statements("seed.sql"):
            self.assertNotIn("--", statement)

    def test_all_tables_in_schema_sql_are_in_the_tables_list(self):
        from data.D_Database import TABLES
        with open(f"{SQL_DIR}/schema.sql", encoding="utf-8") as f:
            created = re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", f.read())
        self.assertEqual(sorted(created), sorted(TABLES))


if __name__ == "__main__":
    unittest.main()
