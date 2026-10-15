"""A patient's QR code. It holds the patient's MedScan ID and nothing else, never any health information."""
import re

import segno


class QRCode:
    """A real, scannable QR code for one MedScan ID, such as PT-2026-01001.
    Encapsulation: the text inside is private and can only be read, never changed.
    Abstraction: the rest of the system asks for svg() or reads a scan with patient_id_from(), and never has to know
    how the segno library draws the code or what a valid MedScan code looks like."""

    PATIENT_CODE = re.compile(r"^PT-\d{4}-(\d{5})$")   # what a patient's code holds: PT-<year>-<5-digit ID>

    def __init__(self, text):
        self.__text = str(text)

    @property
    def text(self):
        """What the code holds, for example PT-2026-01001."""
        return self.__text

    def svg(self):
        """The code drawn as an SVG picture, ready to put in a page. The same ID always gives the same picture."""
        code = segno.make_qr(self.__text, error="m")   # "m": still reads if about 15% of it is smudged or covered
        return code.svg_inline(dark="#0F1E2E", light="#fff", border=2, svgclass="qr", omitsize=True,
                               title=f"QR code for {self.__text}")

    @classmethod
    def patient_id_from(cls, scanned_text):
        """The patient ID inside a scanned code ('PT-2026-01001' -> 1001), or None if it is not a MedScan
        patient code (a doctor's ID, a web address, any other QR code)."""
        match = cls.PATIENT_CODE.match((scanned_text or "").strip())
        return int(match.group(1)) if match else None
