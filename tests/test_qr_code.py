"""The QR code: a patient's code holds only their MedScan ID, and scanning it does exactly what typing the ID does."""
import unittest

from django.test import Client

from models.M_QR_Code import QRCode
from tests.helpers import count, fresh_system, html, login


class TheCode(unittest.TestCase):
    """The QRCode class on its own, no database needed."""

    def test_it_holds_the_id_and_the_id_cannot_be_changed(self):
        code = QRCode("PT-2026-01001")
        self.assertEqual(code.text, "PT-2026-01001")
        with self.assertRaises(AttributeError):
            code.text = "PT-2026-09999"

    def test_it_is_drawn_as_an_svg_picture(self):
        picture = QRCode("PT-2026-01001").svg()
        self.assertTrue(picture.startswith("<svg"))
        self.assertIn('class="qr"', picture)
        self.assertIn("viewBox", picture)

    def test_a_scanned_patient_code_gives_the_patient_id(self):
        self.assertEqual(QRCode.parse("PT-2026-01001"), (1001, None))
        self.assertEqual(QRCode.parse("  PT-2025-01042\n"), (1042, None))

    def test_anything_else_is_not_a_patient_code(self):
        for text in ("DR-2026-02001", "https://example.com/PT-2026-01001", "1001", "PT-2026-1001", "", None):
            self.assertEqual(QRCode.parse(text), (None, None), text)


class ScanningAPatient(unittest.TestCase):
    """The pages: the patient's code, the doctor's scanner, and what happens after a scan."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def test_the_patient_sheet_asks_for_their_real_code_and_it_is_never_in_the_page(self):
        page = html(self.pat.get("/dashboard/"))
        self.assertIn('id="qr-picture"', page)
        self.assertNotIn("<svg viewBox", page.split('id="qr-sheet"')[1].split("</dialog>")[0])   # drawn after it opens
        data = self.pat.get("/qr/code/").json()
        self.assertIn("QR code for PT-2026-01001", data["svg"])
        self.assertNotIn(self.s.current_qr(1001).value, data["svg"])         # the secret is in the picture, not in the text

    def test_a_patients_code_comes_from_their_own_id(self):
        patient = self.s.get_patient(1001)
        self.assertEqual(patient.qr_code().text, "PT-2026-01001")
        token = self.s.current_qr(1001)
        self.assertEqual(patient.qr_code(token).text, f"PT-2026-01001:{token.value}")

    def test_the_doctor_page_is_camera_only(self):
        page = html(self.doc.get("/qr/"))
        for part in ('id="qr-video"', 'id="qr-status"', 'id="qr-retry"', 'id="qr-canvas"'):
            self.assertIn(part, page)
        for gone in ('id="qr-file"', 'id="qr-start"', "Upload a photo of the code"):
            self.assertNotIn(gone, page)
        self.assertIn("/static/js/vendor/jsQR.js", page)
        self.assertIn("/static/js/G_Scan.js", page)

    def test_only_the_doctor_page_loads_the_scanner(self):
        self.assertNotIn("G_Scan.js", html(self.pat.get("/qr/", follow=True)))

    def test_a_plain_id_code_lands_on_the_locked_patient_page(self):
        response = self.doc.get("/qr/scan/?code=PT-2026-01001")
        self.assertEqual(response["Location"], "/patient/1001/")
        page = html(self.doc.get(response["Location"]))
        self.assertIn("Juan Dela Cruz", page)
        self.assertIn("Record locked", page)

    def test_a_plain_id_scan_never_asks_for_or_opens_access_by_itself(self):
        page = html(self.doc.get("/qr/scan/?code=PT-2026-01001", follow=True))
        self.assertEqual(count("tb_access_requests"), 0)
        self.assertFalse(self.s.has_access(2001, 1001))
        self.assertNotIn("Penicillin", page)
        self.assertNotIn("Consultation notes", page)

    def test_a_code_that_is_not_a_patient_code_goes_back_with_a_message(self):
        response = self.doc.get("/qr/scan/?code=https://example.com", follow=True)
        self.assertEqual(response.redirect_chain[-1][0], "/qr/")
        self.assertIn("That is not a MedScan patient code.", html(response))

    def test_only_doctors_can_scan(self):
        self.assertEqual(self.pat.get("/qr/scan/?code=PT-2026-01001")["Location"], "/dashboard/")
        self.assertEqual(Client().get("/qr/scan/?code=PT-2026-01001")["Location"], "/dashboard/")


if __name__ == "__main__":
    unittest.main()
