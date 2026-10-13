"""The one place that talks to MySQL: connections, transactions, and building the tables from the SQL files.
Needs PyMySQL:  python -m pip install -r requirements.txt"""
import os
import re
import threading
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT_DIR, "database")
SCHEMA_VERSION = 4  # must match the number inserted at the bottom of database/schema.sql
# Children come before their parents, so foreign keys never block a delete.
TABLES = ["notifications", "record_views", "emergency_logs", "access_requests", "consultations",
          "record_items", "patients", "doctors", "schema_version"]
FIRST_ID = {"doctors": 2001, "patients": 1001}  # every other table counts from 1
# Strict mode: the database refuses bad data (missing values, unknown choices, text that is too long)
# instead of quietly storing something else.
STRICT_MODE = "STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION"
UNKNOWN_DATABASE = 1049  # MySQL's error number for "that database does not exist"


class DatabaseError(RuntimeError):
    """The database cannot be reached or is not in the shape this version of MedScan expects."""


class Transaction:
    """One database transaction: every query made while it is open shares one connection and is saved together
    (commit) or not at all (rollback). The connection is only opened when the first query is made."""

    def __init__(self, db):
        self._db = db
        self._conn = None

    @property
    def connection(self):
        """The connection, opened on first use."""
        if self._conn is None:
            self._conn = self._db.connect()
        return self._conn

    def commit(self):
        """Save everything done in this transaction."""
        self._finish(commit=True)

    def rollback(self):
        """Undo everything done in this transaction."""
        self._finish(commit=False)

    def _finish(self, commit):
        """End the transaction and give the connection back."""
        conn, self._conn = self._conn, None
        if self._db._local.tx is self:
            self._db._local.tx = None
        if conn is not None:
            try:
                conn.commit() if commit else conn.rollback()
            finally:
                conn.close()


class Database:
    """Opens connections and runs queries. Repositories use cursor(); anything that must succeed or fail
    as one piece goes inside unit_of_work(). The website opens one transaction per web request (see
    gui/G_Middleware.py), so all the queries of one page share a single connection."""

    def __init__(self, host="127.0.0.1", port=3306, user="root", password="", name="db_medscan"):
        self.host, self.port, self.user = host, int(port), user
        self.password, self.name = password, name
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):  # the name ends up inside SQL text, so keep it plain
            raise ValueError(f"Invalid database name: {name!r}")
        self._local = threading.local()  # each web request thread has its own transaction
        self._local.tx = None

    @classmethod
    def from_environment(cls, name=None):
        """Read the connection settings from MEDSCAN_DB_* variables (defaults suit a local XAMPP).
        name overrides the database name."""
        env = os.environ.get
        return cls(env("MEDSCAN_DB_HOST", "127.0.0.1"), env("MEDSCAN_DB_PORT", "3306"),
                   env("MEDSCAN_DB_USER", "root"), env("MEDSCAN_DB_PASSWORD", ""),
                   name or env("MEDSCAN_DB_NAME", "db_medscan"))

    # ---- connections ----
    def _open(self, database):
        """One raw connection. database=None connects to the server only."""
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
        """Open a connection to the MedScan database, creating the (empty) database first if it is missing."""
        try:
            return self._open(self.name)
        except pymysql.err.OperationalError:
            pass  # only reached for "unknown database"
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
        """Start a transaction on this thread. The caller must end it with commit() or rollback()."""
        if self.in_transaction:
            raise RuntimeError("A transaction is already open on this thread.")
        self._local.tx = Transaction(self)
        return self._local.tx

    @contextmanager
    def unit_of_work(self):
        """Everything inside the block is saved together, or not at all. Inside a transaction that is
        already open (such as the web request's) it simply joins it."""
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
        """A cursor that returns rows as dictionaries. Inside a transaction it joins that transaction;
        on its own it saves right after the block."""
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
        """The SQL statements in one of the .sql files (comments removed)."""
        with open(os.path.join(SQL_DIR, filename), encoding="utf-8") as f:
            text = re.sub(r"--[^\n]*", "", f.read())
        return [statement.strip() for statement in text.split(";") if statement.strip()]

    def prepare(self):
        """Make the database ready: create any missing tables (database/schema.sql) and, if there are no
        users at all, add the test accounts (database/seed.sql)."""
        with self.unit_of_work():
            with self.cursor() as cur:
                if self._is_outdated(cur):
                    raise DatabaseError(
                        f"The tables in '{self.name}' come from an older version of MedScan. "
                        "Run:  python reset_database.py   (this empties the MedScan tables and rebuilds them).")
                for statement in self._statements("schema.sql"):
                    cur.execute(statement)
                cur.execute("SELECT (SELECT COUNT(*) FROM patients) + (SELECT COUNT(*) FROM doctors) AS users")
                if cur.fetchone()["users"] == 0:
                    for statement in self._statements("seed.sql"):
                        cur.execute(statement)

    def _is_outdated(self, cur):
        """True if MedScan tables exist from a different version of the schema."""
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'patients'", (self.name,))
        if cur.fetchone()["n"] == 0:
            return False  # a fresh database
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'schema_version'", (self.name,))
        if cur.fetchone()["n"] == 0:
            return True
        cur.execute("SELECT version FROM schema_version")
        row = cur.fetchone()
        return row is None or row["version"] != SCHEMA_VERSION

    def reset(self):
        """Delete every MedScan table and build them again with the test accounts. Used by reset_database.py."""
        with self.unit_of_work():
            with self.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in TABLES:
                    cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        self.prepare()

    def reset_data(self):
        """Empty every table and add the test accounts again, without rebuilding the tables (for tests;
        call prepare() once first so the tables exist)."""
        data_tables = [t for t in TABLES if t != "schema_version"]
        with self.unit_of_work():
            with self.cursor() as cur:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in data_tables:
                    cur.execute(f"DELETE FROM `{table}`")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        with self.cursor() as cur:
            for table in data_tables:  # DELETE leaves the ID counters running, so put them back
                cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = {FIRST_ID.get(table, 1)}")
        with self.unit_of_work():
            with self.cursor() as cur:
                for statement in self._statements("seed.sql"):
                    cur.execute(statement)
