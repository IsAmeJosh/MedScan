"""The one place that talks to MySQL: it opens connections, runs transactions, and builds the tables from the SQL
files in database/. It needs PyMySQL (python -m pip install -r requirements.txt)."""
import os
import re
import threading
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT_DIR, "database")
SCHEMA_VERSION = 3  # Must match the number inserted at the bottom of database/schema.sql.
# Children come before their parents, so foreign keys never block a delete.
TABLES = ["tb_health_log", "tb_health_items", "tb_qr_scans", "tb_qr_tokens", "tb_notifications", "tb_record_views", "tb_emergency_logs", "tb_access_requests",
          "tb_consultations", "tb_medical_items", "tb_patients", "tb_doctors", "tb_schema_version"]
# The table names from before the tb_ naming. Old layouts are not upgraded; reset() just removes these too, so a reset
# leaves no old tables behind in phpMyAdmin.
OLD_TABLES = ["qr_scans", "qr_tokens", "notifications", "record_views", "emergency_logs", "access_requests", "consultations",
              "record_items", "patients", "doctors", "schema_version"]
FIRST_ID = {"tb_doctors": 2001, "tb_patients": 1001}  # Every other table counts its IDs from 1.
DEMO_MARKER_MOBILE = "09171110001"  # The first sample patient in database/demo_data.sql: its presence means the sample data is in.
# Strict mode: the database refuses bad data (missing values, unknown choices, text that is too long)
# instead of quietly storing something else.
STRICT_MODE = "STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION"
UNKNOWN_DATABASE = 1049  # MySQL's error number for "that database does not exist"
MIGRATIONS = {1: "migrate_1_to_2.sql", 2: "migrate_2_to_3.sql"}  # the upgrade that takes each old version one step forward
ALREADY_THERE = (1060, 1826, 3822)  # "duplicate column" and "duplicate check" errors: the migration skips them


class DatabaseError(RuntimeError):
    """Raised when the database cannot be reached, or when its tables come from a version of MedScan this one does not
    understand. The message says what happened and what to do next."""


class Transaction:
    """One database transaction: every query made while it is open shares one connection, and the changes are saved
    together (commit) or not at all (rollback). The Database makes one per web request. The connection is only
    opened when the first query is made."""

    def __init__(self, db):
        """Start with no connection. One is opened the first time a query is made."""
        self._db = db
        self._conn = None

    @property
    def connection(self):
        """The connection, opened the first time it is needed. A page that never asks the database anything never
        opens one."""
        if self._conn is None:
            self._conn = self._db.connect()
        return self._conn

    def commit(self):
        """Save everything that was done during this transaction."""
        self._finish(commit=True)

    def rollback(self):
        """Undo everything that was done during this transaction."""
        self._finish(commit=False)

    def _finish(self, commit):
        """End the transaction and hand the connection back, whether the changes were saved or undone."""
        conn, self._conn = self._conn, None
        if self._db._local.tx is self:
            self._db._local.tx = None
        if conn is not None:
            try:
                conn.commit() if commit else conn.rollback()
            finally:
                conn.close()


class Database:
    """Opens connections and runs queries. Repositories call cursor() to run SQL, and anything that has to succeed or
    fail as one piece goes inside unit_of_work(). The website opens one transaction per web request (see
    gui/G_Middleware.py), so every query of one page shares a single connection."""

    def __init__(self, host="127.0.0.1", port=3306, user="root", password="", name="db_medscan"):
        """Remember where the database is. The name is checked because it ends up inside SQL text, so only letters,
        digits and underscores are allowed."""
        self.host, self.port, self.user = host, int(port), user
        self.password, self.name = password, name
        # The name ends up inside SQL text, so only plain characters are allowed.
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            raise ValueError(f"Invalid database name: {name!r}")
        self._local = threading.local()  # Every web request runs on its own thread and gets its own transaction.
        self._local.tx = None

    @classmethod
    def from_environment(cls, name=None):
        """Build a Database from the MEDSCAN_DB_* environment variables. The defaults suit a local XAMPP, so nothing
        needs to be set on a normal laptop. name replaces the database name (the tests and the console demo each
        use a database of their own)."""
        env = os.environ.get
        return cls(env("MEDSCAN_DB_HOST", "127.0.0.1"), env("MEDSCAN_DB_PORT", "3306"),
                   env("MEDSCAN_DB_USER", "root"), env("MEDSCAN_DB_PASSWORD", ""),
                   name or env("MEDSCAN_DB_NAME", "db_medscan"))

    # ---- connections ----
    def _open(self, database):
        """Open one raw connection. With database=None it connects to the MySQL server only, which is how a missing
        database gets created."""
        try:
            return pymysql.connect(host=self.host, port=self.port, user=self.user, password=self.password,
                                   database=database, charset="utf8mb4", connect_timeout=3,
                                   cursorclass=DictCursor, autocommit=False, sql_mode=STRICT_MODE)
        except pymysql.err.OperationalError as error:
            if error.args and error.args[0] == UNKNOWN_DATABASE:
                raise
            raise DatabaseError(f"Connection error: could not reach the database at "
                                f"{self.host}:{self.port} as '{self.user}' ({error}).") from error

    def connect(self):
        """Open a connection to the MedScan database. If the database does not exist yet it is created (empty) first,
        so a fresh laptop works at the first start."""
        try:
            return self._open(self.name)
        except pymysql.err.OperationalError:
            pass  # We only get here for the "unknown database" error.
        conn = self._open(None)
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.name}` "
                            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
        finally:
            conn.close()
        return self._open(self.name)

    # ---- transactions and cursors ----
    @property
    def in_transaction(self):
        """True while a transaction is open on this thread."""
        return getattr(self._local, "tx", None) is not None

    def begin(self):
        """Start a transaction on this thread. Whoever starts it must end it with commit() or rollback()."""
        if self.in_transaction:
            raise RuntimeError("A transaction is already open on this thread.")
        self._local.tx = Transaction(self)
        return self._local.tx

    @contextmanager
    def unit_of_work(self):
        """A block of work that is saved together or not at all. Wrap several writes in it when they only make sense
        as a set. If a transaction is already open (a web request opens one) the block simply joins it."""
        if self.in_transaction:
            yield
            return
        tx = self.begin()
        try:
            yield
            tx.commit()
        except BaseException:
            tx.rollback()
            raise

    @contextmanager
    def cursor(self):
        """A cursor that returns every row as a dictionary, so code reads row["name"] instead of counting columns.
        Inside a transaction it joins that transaction; on its own it saves right after the block."""
        tx = getattr(self._local, "tx", None)
        if tx is not None:
            with tx.connection.cursor() as cur:
                yield cur
            return
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---- building and resetting ----
    @staticmethod
    def _statements(filename):
        """Read one of the .sql files and return its SQL statements, with the comments taken out."""
        with open(os.path.join(SQL_DIR, filename), encoding="utf-8") as f:
            text = re.sub(r"--[^\n]*", "", f.read())
        return [statement.strip() for statement in text.split(";") if statement.strip()]

    def prepare(self):
        """Make the database ready to use: create any missing tables (database/schema.sql) and, if there are no users yet,
        add the demo accounts (database/seed.sql). It is safe to run on every start. An older MedScan database
        (version 1 or 2) is upgraded in place, step by step (database/migrate_*.sql), and keeps its data. Tables from any older MedScan are refused with a
        message, because those layouts are not upgraded: reset_database.py rebuilds them."""
        with self.unit_of_work():
            with self.cursor() as cur:
                while self._version(cur) in MIGRATIONS:                    # 1 -> 2 -> 3, each step run once
                    self._run_migration(cur, MIGRATIONS[self._version(cur)])
                if self._is_outdated(cur):
                    raise DatabaseError(
                        f"The tables in '{self.name}' come from an older version of MedScan. "
                        "Run:  python reset_database.py   (this empties the MedScan tables and rebuilds them).")
                for statement in self._statements("schema.sql"):
                    cur.execute(statement)
                cur.execute("SELECT (SELECT COUNT(*) FROM tb_patients) + (SELECT COUNT(*) FROM tb_doctors) AS users")
                if cur.fetchone()["users"] == 0:
                    for statement in self._statements("seed.sql"):
                        cur.execute(statement)

    def _version(self, cur):
        """The layout version stored in the database, or None when there is no version table (a fresh database, or tables
        from before MedScan kept a version)."""
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'tb_schema_version'", (self.name,))
        if cur.fetchone()["n"] == 0:
            return None
        cur.execute("SELECT version FROM tb_schema_version")
        row = cur.fetchone()
        return row["version"] if row else None

    def _upgrade_1_to_2(self, cur):
        """Run database/migrate_1_to_2.sql (a patient's height, weight and emergency contact)."""
        self._run_migration(cur, "migrate_1_to_2.sql")

    def _upgrade_2_to_3(self, cur):
        """Run database/migrate_2_to_3.sql (the health items: allergies, conditions, medications and vaccines)."""
        self._run_migration(cur, "migrate_2_to_3.sql")

    def _run_migration(self, cur, filename):
        """Run one migration file. A column or check that is already there (the migration ran halfway before) is skipped
        instead of stopping the start-up."""
        for statement in self._statements(filename):
            try:
                cur.execute(statement)
            except pymysql.err.Error as error:
                if error.args[0] not in ALREADY_THERE:
                    raise

    def _is_outdated(self, cur):
        """True if the database already has tables but they are not the current layout (they come from an older MedScan)."""
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s", (self.name,))
        if cur.fetchone()["n"] == 0:
            return False  # a fresh database
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'tb_schema_version'", (self.name,))
        if cur.fetchone()["n"] == 0:
            return True
        cur.execute("SELECT version FROM tb_schema_version")
        row = cur.fetchone()
        return row is None or row["version"] != SCHEMA_VERSION

    def reset(self):
        """Delete every MedScan table (including the tables of older versions) and build them again with the demo accounts.
        This is what reset_database.py runs."""
        with self.unit_of_work():
            with self.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in TABLES + OLD_TABLES:
                    cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        self.prepare()

    def reset_data(self):
        """Empty every table and add the demo accounts again, without rebuilding the tables. It is much faster than
        reset(), which is why the tests use it (call prepare() once first so the tables exist)."""
        data_tables = [t for t in TABLES if t != "tb_schema_version"]
        with self.unit_of_work():
            with self.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in data_tables:
                    cur.execute(f"DELETE FROM `{table}`")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        with self.cursor() as cur:
            # DELETE leaves the ID counters running, so they are put back to where a fresh database starts.
            for table in data_tables:
                cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = {FIRST_ID.get(table, 1)}")
        with self.unit_of_work():
            with self.cursor() as cur:
                for statement in self._statements("seed.sql"):
                    cur.execute(statement)

    def add_demo_data(self):
        """Add the sample doctors, patients and history from database/demo_data.sql on top of the demo accounts, so the
        screens look lived-in for a demo. Returns True when it was added, or False (adding nothing) when it is already
        there. It needs the demo accounts from seed.sql."""
        with self.unit_of_work():
            with self.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM tb_patients WHERE mobile_number = %s", (DEMO_MARKER_MOBILE,))
                if cur.fetchone()["n"]:
                    return False
                for statement in self._statements("demo_data.sql"):
                    cur.execute(statement)
        return True
