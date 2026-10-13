"""Test setup. Runs before any test: the tests use their own database, db_medscan_test,
so the data the website uses (db_medscan) is never touched."""
import logging
import os

os.environ["MEDSCAN_DB_NAME"] = "db_medscan_test"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medscan_site.settings")
logging.disable(logging.ERROR)  # hides the errors the tests cause on purpose (rejected forms, a page that breaks)

from data.D_Database import Database, DatabaseError  # noqa: E402

_test_database = Database.from_environment()
try:
    _test_database.prepare()
except DatabaseError as error:
    if "older version" not in str(error):
        raise
    _test_database.reset()   # a new version of the tables: build them again

import django  # noqa: E402

django.setup()
