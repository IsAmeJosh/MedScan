"""Runs the page scripts for real, with the JavaScript engine that is built into Windows (cscript).
- format_test.js: the phone and date formatting and the form rules, 150 checks.
- smoke_test.js: every script parses and starts without an error.
Skipped on a computer without cscript. What those scripts do on a live page (clicks, pop-ups, the cursor) still
needs a person with a browser: the list is in the README."""
import shutil
import subprocess
import unittest
from pathlib import Path

JS_TESTS = Path(__file__).resolve().parent / "js"
STATIC_JS = Path(__file__).resolve().parent.parent / "gui" / "static" / "js"


@unittest.skipUnless(shutil.which("cscript"), "needs Windows Script Host (cscript)")
class RunScripts(unittest.TestCase):
    def run_script(self, name):
        result = subprocess.run(["cscript", "//nologo", str(JS_TESTS / name)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ALL PASS", result.stdout)
        return result.stdout

    def test_formatting_and_form_rules(self):
        self.assertIn("checks", self.run_script("format_test.js"))

    def test_every_page_script_starts_cleanly(self):
        output = self.run_script("smoke_test.js")
        for script in STATIC_JS.glob("G_*.js"):
            if script.name != "G_Format.js":
                self.assertIn(script.name, output, f"{script.name} is not covered by the start-up test")


class ScriptStyle(unittest.TestCase):
    """The scripts are written in plain old-style JavaScript so the test engine can run them, and so they work
    in any browser. Keep it that way."""

    def test_no_newer_syntax_in_the_scripts(self):
        for script in STATIC_JS.glob("G_*.js"):
            text = script.read_text(encoding="utf-8")
            code = "\n".join(line.split("//")[0] for line in text.splitlines())
            for forbidden in ["=>", "`", "\nlet ", "\nconst ", " let ", " const "]:
                self.assertNotIn(forbidden, code, f"{script.name} uses {forbidden!r}")

    def test_scripts_do_not_load_anything_from_the_internet(self):
        for script in STATIC_JS.glob("G_*.js"):
            self.assertNotIn("http://", script.read_text(encoding="utf-8"), script.name)
            self.assertNotIn("https://", script.read_text(encoding="utf-8"), script.name)


if __name__ == "__main__":
    unittest.main()
