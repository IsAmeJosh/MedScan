"""A patient's QR code. It holds the patient's MedScan ID and, when it is a live code, a one-time secret.
It never holds any health information."""
import re

import segno


class QRCode:
    """A real, scannable QR code for one piece of text, such as PT-2026-01001 or PT-2026-01001:<secret>.
    Encapsulation: the text inside is private and can only be read, never changed.
    Abstraction: the rest of the system asks for svg() or reads a scan with parse(), and never has to know
    how the segno library draws the code or what a valid MedScan code looks like."""

    # Matches PT-<year>-<5-digit ID>, optionally followed by ":" and the 32-character one-time secret.
    PATIENT_CODE = re.compile(r"^PT-\d{4}-(\d{5})(?::([0-9a-f]{32}))?$")

    def __init__(self, text):
        """Keep the text to draw. It is private and cannot be changed afterwards (encapsulation)."""
        self.__text = str(text)

    @property
    def text(self):
        """What the code holds, for example PT-2026-01001."""
        return self.__text

    @classmethod
    def with_secret(cls, display_id, secret):
        """The live code for a patient: their display ID and the one-time secret joined by a colon, such as
        PT-2026-01001:3fa9..."""
        return cls(f"{display_id}:{secret}")

    def svg(self):
        """The code drawn as an SVG picture, ready to put in a page. The same text always gives the same picture."""
        # Error correction level "m": the code still reads if about 15% of it is smudged or covered.
        code = segno.make_qr(self.__text, error="m")
        return code.svg_inline(dark="#0F1E2E", light="#fff", border=2, svgclass="qr", omitsize=True,
                               # The picture's title never includes the secret.
                               title=f"QR code for {self.__text.split(':')[0]}")

    @classmethod
    def parse(cls, scanned_text):
        """Read a scanned code and return (patient ID, secret), for example (1001, '3fa9...'). The secret is None for
        a plain ID code. If the text is not a MedScan patient code at all (a doctor's ID, a web address, anything
        else) it returns (None, None)."""
        match = cls.PATIENT_CODE.match((scanned_text or "").strip())
        return (int(match.group(1)), match.group(2)) if match else (None, None)
