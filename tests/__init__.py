"""Test setup. Runs before any test: the tests must never touch real data,
so the website is told to save nowhere (memory) while they run."""
import logging
import os

os.environ["MEDSCAN_STORE"] = "memory"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medscan_site.settings")
logging.disable(logging.WARNING)  # hides the expected "Forbidden" warnings from the security tests

import django  # noqa: E402

django.setup()
