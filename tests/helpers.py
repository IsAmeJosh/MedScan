"""Shared helpers for the tests. Every test starts from the test accounts in database/seed.sql:
doctor 2001 (Reyes, password doc123) and patient 1001 (Juan Dela Cruz, password pat123)."""
import itertools

from django.test import Client

from gui import G_Views

PASSWORD = "secret1"   # a valid password for accounts the tests create
BORN = "1990-05-20"    # a valid date of birth


_numbers = itertools.count(1000000)


def next_mobile():
    """A mobile number nobody has used yet (every patient needs their own)."""
    return f"0917{next(_numbers):07d}"


def new_patient(system, name, password, sex, born, *args, **kwargs):
    """system.register_patient, with a fresh mobile number unless the test gives one."""
    kwargs.setdefault("contact_number", next_mobile())
    return system.register_patient(name, password, sex, born, *args, **kwargs)


_seeded = False


def _seed_once():
    """The first time a test needs the database, reset it to the test accounts (the rest of the run relies on them)."""
    global _seeded
    if not _seeded:
        G_Views.db.prepare()
        G_Views.db.reset_data()
        _seeded = True


def fresh_system(test):
    """The system the website uses, on a database holding just the test accounts.
    The whole test runs inside one transaction that is rolled back afterwards, so tests never affect each
    other and run fast. (ID counters keep counting, so tests must use the IDs they are given.)"""
    _seed_once()
    transaction = G_Views.db.begin()
    test.addCleanup(transaction.rollback)
    return G_Views.system


def committed_system(test):
    """Like fresh_system, but changes are really saved (committed) and the database is reset afterwards.
    Slower, so only for tests about saving itself: persistence, transactions, several users at once."""
    G_Views.db.reset_data()
    test.addCleanup(G_Views.db.reset_data)
    return G_Views.system


def rows(sql, *params):
    """Run a SELECT straight on the database and return the rows (to check what really got saved)."""
    with G_Views.db.cursor() as cur:
        cur.execute(sql, params or None)
        return cur.fetchall()


def count(table, where="1 = 1", *params):
    """How many rows a table has."""
    return rows(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", *params)[0]["n"]


def execute(sql, *params):
    """Run an UPDATE or similar straight on the database (used to make saved timestamps older)."""
    with G_Views.db.cursor() as cur:
        cur.execute(sql, params or None)


def age_emergencies(minutes):
    """Pretend every emergency override happened `minutes` minutes earlier."""
    execute("UPDATE tb_emergency_logs SET created_at = created_at - INTERVAL %s MINUTE", minutes)


def age_views(minutes):
    """Pretend every record view happened `minutes` minutes earlier."""
    execute("UPDATE tb_record_views SET created_at = created_at - INTERVAL %s MINUTE", minutes)


def login(user_id, password):
    """A browser that is logged in."""
    client = Client()
    client.post("/", {"user_id": str(user_id), "password": password})
    return client


def html(response):
    """The page text of a response."""
    return response.content.decode()


def approve(system, doctor_id=2001, patient_id=1001):
    """Give a doctor the patient's approval. Returns the request."""
    request = system.request_access(system.get_doctor(doctor_id), patient_id)
    system.respond_to_request(request.request_id, patient_id, True)
    return request


def build_sample_data(system):
    """Put something in every table: used by the persistence tests."""
    reyes = system.get_doctor(2001)
    santos = system.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview Medical Center")
    ana = system.register_patient("Ana Lopez", "ana123", "Female", "1998-02-01", "Latex, Dust", "",
                                  contact_number="09281112222", medications="Cetirizine", blood_type="A+")
    approved = approve(system)
    system.add_consultation(reyes, 1001, "Headache for 3 days. Rest advised. Café intake reduced.")
    system.add_consultation(reyes, 1001, "Follow-up: resolved.")
    system.open_record(reyes, 1001)
    denied = system.request_access(santos, 1001)
    system.respond_to_request(denied.request_id, 1001, False)
    system.request_access(santos, ana.user_id)
    system.emergency_access(santos, 1001, "Patient unconscious on arrival")
    system.revoke_access(approved.request_id, 1001)
    system.mark_inbox_read(1001)
    return santos, ana
