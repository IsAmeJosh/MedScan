"""Guards against typos in the templates: every icon and every page name that a template uses must exist."""
import re
import unittest
from pathlib import Path

from django.urls import get_resolver

from gui.G_Icons import ICONS

TEMPLATES = Path(__file__).resolve().parent.parent / "gui" / "templates"


class TemplateNames(unittest.TestCase):
    def test_every_icon_used_exists(self):
        for path in TEMPLATES.glob("*.html"):
            for name in re.findall(r'\{% icon "([^"]+)"', path.read_text(encoding="utf-8")):
                self.assertIn(name, ICONS, f"{path.name} uses an icon that does not exist: {name}")

    def test_every_page_name_used_exists(self):
        known = {name for name in get_resolver().reverse_dict if isinstance(name, str)}
        for path in TEMPLATES.glob("*.html"):
            for name in re.findall(r"\{% url '([^']+)'", path.read_text(encoding="utf-8")):
                self.assertIn(name, known, f"{path.name} links to a page that does not exist: {name}")

    def test_every_script_and_stylesheet_a_template_loads_exists(self):
        static = TEMPLATES.parent / "static"
        for path in TEMPLATES.glob("*.html"):
            for name in re.findall(r"\{% static '([^']+)' %\}", path.read_text(encoding="utf-8")):
                self.assertTrue((static / name).exists(), f"{path.name} loads a file that does not exist: {name}")

    def test_every_included_template_exists(self):
        for path in TEMPLATES.glob("*.html"):
            for name in re.findall(r'\{% (?:include|extends) "([^"]+)"', path.read_text(encoding="utf-8")):
                self.assertTrue((TEMPLATES / name).exists(), f"{path.name} uses a template that does not exist: {name}")


if __name__ == "__main__":
    unittest.main()
