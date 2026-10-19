"""Every pop-up that dims the page: one shared script and one shared markup rule (a Cancel button or a round x), and the top-bar search
box that was double-boxed."""
import re
import unittest
from pathlib import Path

from tests.helpers import approve, fresh_system, html, login

ROOT = Path(__file__).resolve().parent.parent / "gui"
CSS = (ROOT / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")


def dialogs(page):
    """Every <dialog ...> ... </dialog> on a page, as (id, html)."""
    return [(m.group(1), m.group(0)) for m in re.finditer(r'<dialog id="([^"]+)".*?</dialog>', page, re.S)]


class SharedBehaviour(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def test_the_shared_script_is_on_every_page_before_the_sheets_script(self):
        for client, url in ((self.pat, "/dashboard/"), (self.doc, "/dashboard/"), (self.pat, "/record/?tab=info"), (self.doc, "/settings/")):
            page = html(client.get(url))
            self.assertIn("G_Overlays.js", page)
            self.assertLess(page.index("G_Overlays.js"), page.index("G_Sheets.js"))

    def test_the_script_says_the_rules_once(self):
        script = (ROOT / "static" / "js" / "G_Overlays.js").read_text(encoding="utf-8")
        for part in ("getBoundingClientRect", "form.reset()", "trigger.focus()", "idle-dialog", "scrim", "'close'"):
            self.assertIn(part, script)
        sheets = (ROOT / "static" / "js" / "G_Sheets.js").read_text(encoding="utf-8")
        self.assertNotIn("tagName === 'DIALOG'", sheets)                      # the outside press is not handled a second time

    def test_every_sheet_and_question_on_the_pages_has_a_cancel_button_or_a_round_x(self):
        approve(self.s)
        self.s.request_access(self.s.register_doctor("Antonio Santos", "secret1", "Cardiology"), 1001)
        pages = [self.pat.get("/dashboard/"), self.pat.get("/record/?tab=info"), self.pat.get("/record/?tab=medical"), self.pat.get("/profile/"),
                 self.pat.get("/access/?tab=requests"), self.doc.get("/dashboard/"), self.doc.get("/patient/1001/"), self.doc.get("/settings/")]
        seen = set()
        for response in pages:
            for sheet_id, markup in dialogs(html(response)):
                if sheet_id == "idle-dialog":
                    continue                                                  # the timer warning is answered, not dismissed
                seen.add(sheet_id.split("-")[0])
                self.assertTrue("data-close" in markup or 'value="cancel"' in markup, f"{sheet_id} has no way out")
        for expected in ("qr", "review", "edit", "confirm"):
            self.assertIn(expected, seen)

    def test_the_review_sheet_has_a_round_x_in_its_top_right_corner(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        sheet = re.search(r'<dialog id="review-\d+".*?</dialog>', html(self.pat.get("/dashboard/")), re.S).group(0)
        self.assertIn('class="ibtn flat close-x" data-close aria-label="Close"', sheet)
        self.assertIn(".sheet.review .close-x{position:absolute;top:14px;right:14px}", CSS)

    def test_the_emergency_question_has_cancel_and_the_logout_question_has_stay(self):
        locked = html(self.doc.get("/patient/1001/"))
        emergency = dict(dialogs(locked))["emergency-sheet"]
        self.assertIn("data-close>Cancel</button>", emergency)
        logout = html(self.pat.get("/logout/"))
        self.assertIn('class="scrim" role="dialog"', logout)
        self.assertRegex(logout, r'<a class="btn lg" href="/settings/">Stay</a>')

    def test_the_idle_warning_is_the_one_pop_up_left_out(self):
        page = html(self.pat.get("/dashboard/"))
        self.assertIn('<dialog id="idle-dialog" class="modal">', page)
        self.assertIn("idle-dialog", (ROOT / "static" / "js" / "G_Overlays.js").read_text(encoding="utf-8"))

    def test_the_notification_panel_has_its_round_x_and_gives_the_focus_back_to_the_bell(self):
        page = html(self.pat.get("/dashboard/"))
        self.assertIn('id="close-notifications" aria-label="Close"', page)
        self.assertIn("openBtn.focus()", (ROOT / "static" / "js" / "G_Shell.js").read_text(encoding="utf-8"))

    def test_the_chips_boxes_start_again_when_their_sheet_is_closed(self):
        self.assertIn("addEventListener('reset'", (ROOT / "static" / "js" / "G_Chips.js").read_text(encoding="utf-8"))


class TopBarSearch(unittest.TestCase):
    def test_it_is_one_box_42_pixels_tall_with_one_soft_ring_on_focus_and_a_full_height_cursor(self):
        box = re.search(r"\.tsearch\{([^}]*)\}", CSS).group(1)
        for part in ("height:42px", "border:1px solid var(--line)", "border-radius:12px", "background:#fff"):
            self.assertIn(part, box)
        self.assertIn(".tsearch:focus-within { border-color:var(--brand); box-shadow:0 0 0 3px var(--brand-tint); }", CSS)
        field = re.search(r"\.tsearch input, \.tsearch input:focus \{([^}]*)\}", CSS).group(1)
        for part in ("flex:1", "height:100%", "border:0", "outline:0", "background:none", "font-size:15px", "line-height:normal",
                     "color:var(--ink)", "caret-color:var(--brand)"):
            self.assertIn(part, field)
        self.assertNotIn("body.searching .tsearch", CSS)                          # no second ring while it is in use
        self.assertNotIn(".tsearch kbd", CSS)

    def test_the_slash_badge_is_gone_and_enter_still_goes_to_the_search_page(self):
        doc = login(2001, "doc123")
        page = html(doc.get("/dashboard/"))
        self.assertNotIn("<kbd", page)
        self.assertRegex(page, r'<form class="tsearch d-only" method="get" action="/search/"')

    def test_pressing_outside_or_escape_closes_it_and_clears_the_typing(self):
        script = (ROOT / "static" / "js" / "G_Suggest.js").read_text(encoding="utf-8")
        self.assertIn("function cancel()", script)
        self.assertIn("input.value = '';", script)
        self.assertIn("document.addEventListener('mousedown'", script)
        self.assertIn("event.key === 'Escape'", script)


if __name__ == "__main__":
    unittest.main()
