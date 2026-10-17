#!/usr/bin/env python
"""Django's command line tool: python manage.py runserver (start the site), python manage.py test (run the tests)."""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medscan_site.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
