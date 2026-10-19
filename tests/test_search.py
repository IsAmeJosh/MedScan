"""The doctor's Search page (reference 25): the box, the live results, the marked matches, the empty and no-match states, and the
privacy rules (strangers only by the whole MedScan ID)."""
import re
import unittest
from pathlib import Path

from django.test import Client

from gui.G_Filters import highlight
from tests.helpers import BORN, PASSWORD, approve, fresh_system, html, login, new_patient


def allow(system, doctor_id, patient_id):
    """The patient allows the doctor in (so the patient becomes one of the doctor's own)."""
    return approve(system, doctor_id, patient_id)


class SearchPage(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.second = new_patient(self.s, "Jose Ramos", PASSWORD, "Male", BORN)       # the IDs themselves depend on the run
        allow(self.s, 2001, 1001)
        allow(self.s, 2001, self.second.user_id)                                      # both are the doctor's own now

    def page(self, query=None):
        return html(self.doc.get("/search/" + (f"?q={query}" if query is not None else "")))

    def results(self, query):
        return html(self.doc.get(f"/search/results/?q={query}"))

    # ---- the page and the box
    def test_the_body_and_main_both_carry_the_search_page_class_and_other_pages_do_not(self):
        page = self.page()
        self.assertIn('<body class="has-shell search-page"', page)
        self.assertIn('<main class="content search-page">', page)
        for url in ("/dashboard/", "/patients/", "/qr/", "/settings/"):
            other = html(self.doc.get(url))
            self.assertNotIn("search-page", other, url)
            self.assertIn('id="top-search-input"', other, url)                      # the small search stays on the other doctor pages

    def test_the_subtitle_is_the_designs(self):
        self.assertIn("Search by MedScan ID or name. You&#x27;ll send them a request to open their record.", self.page().replace("You'll", "You&#x27;ll"))

    def test_the_box_is_the_designs_sx_div_with_a_magnifier_a_real_input_and_a_round_clear_button(self):
        page = self.page()
        box = re.search(r'<div class="sx">.*?</div>', page, re.S).group(0)
        self.assertIn("<svg", box.split("<input")[0])                                # the magnifier comes first
        field = re.search(r"<input[^>]*>", box).group(0)
        for part in ('name="q"', "autofocus", 'aria-label="Search by MedScan ID or name"', 'autocomplete="off"'):
            self.assertIn(part, field)
        self.assertNotIn('type="search"', field)
        self.assertIn('<button type="button" class="clr" id="search-clear" aria-label="Clear" hidden>', box)     # nothing to clear yet
        self.assertNotIn("hidden>", re.search(r'<button type="button" class="clr"[^>]*>', self.page("PT-2026-0")).group(0))   # text in the box: it shows

    def test_the_typed_text_is_carried_over_from_the_top_bar_search_of_the_other_pages(self):
        form = re.search(r'<form class="tsearch d-only"[^>]*>', html(self.doc.get("/dashboard/"))).group(0)
        self.assertIn('action="/search/"', form)
        page = html(self.doc.get("/search/?q=PT-2026-0100"))
        self.assertIn('value="PT-2026-0100"', re.search(r'<input id="search-input"[^>]*>', page).group(0))

    def test_an_empty_box_shows_nothing_below_it(self):
        for page in (self.page(), self.page(""), self.page("J")):                       # nothing, empty, or only one character
            below = page.split('id="search-results"')[1].split("</div>")[0]
            self.assertNotIn("patient", below.split('aria-live="polite">')[1])
            self.assertNotIn("panel", below)

    # ---- results among the doctor's own patients
    def test_part_of_an_id_finds_your_own_patients_with_a_count_and_the_match_marked(self):
        page = self.page("PT-2026-0")                                                    # both IDs start like this
        self.assertIn('<div class="cnt">2 patients found</div>', page)
        self.assertIn("<mark>PT-2026-0</mark>1001", page)
        self.assertIn(f"<mark>PT-2026-0</mark>{self.second.display_id[9:]}", page)
        self.assertLess(page.index("Juan Dela Cruz"), page.index("Jose Ramos"))        # in ID order
        self.assertEqual(page.count('<span class="pill green">Allowed</span>'), 2)

    def test_one_match_says_1_patient_found(self):
        self.assertIn('<div class="cnt">1 patient found</div>', self.page("PT-2026-01001"))

    def test_the_whole_id_or_part_of_it_finds_your_own_patient(self):
        for query in ("PT-2026-01001", "01001", "1001", "pt-2026-01001", "PT 2026 01001".replace(" ", "")):
            self.assertIn("Juan Dela Cruz", self.page(query), query)
        self.assertIn("<mark>1001</mark>", self.page("1001"))

    def test_the_search_ignores_case_and_keeps_the_text_on_the_page_as_it_is(self):
        self.assertIn("<mark>PT-2026-0</mark>1001", self.page("pt-2026-0"))

    def test_a_name_finds_your_own_patients_and_marks_the_name(self):
        page = self.page("jos")
        self.assertIn("<b><mark>Jos</mark>e Ramos</b>", page)
        self.assertIn('<div class="cnt">1 patient found</div>', page)

    def test_at_most_ten_patients_are_listed(self):
        for number in range(11):
            extra = new_patient(self.s, f"Extra Patient {number}", PASSWORD, "Female", BORN)
            allow(self.s, 2001, extra.user_id)
        page = self.page("PT-2026")
        self.assertEqual(len(re.findall(r'<a class="row" href="/patient/', page)), 10)
        self.assertIn('<div class="cnt">10 patients found</div>', page)

    def test_the_typed_text_is_never_run_as_a_wildcard_or_as_markup(self):
        self.assertIn("No patient found", self.page("%25%25"))
        self.assertIn("No patient found", self.page("__"))
        page = self.page("%3Cb%3Ex%3C/b%3E")
        self.assertIn('No patient found for "&lt;b&gt;x&lt;/b&gt;"', page)
        self.assertNotIn("<b>x</b>", page)

    # ---- no match
    def test_no_match_is_one_panel_with_the_designs_two_lines(self):
        page = self.page("PT-2026-9999")
        self.assertIn('<div class="panel"><div class="s-empty"><b>No patient found for "PT-2026-9999"</b>'
                      'Check the ID on their MedScan card, or scan their QR code instead.</div></div>', page)
        self.assertNotIn('class="cnt"', page)

    # ---- as you type
    def test_the_results_part_is_served_on_its_own_for_the_live_updates(self):
        part = self.results("PT-2026-0")
        self.assertNotIn("<html", part)
        self.assertIn("2 patients found", part)
        self.assertEqual(self.results("J").strip(), "")                                 # under two characters: nothing
        self.assertIn("No patient found", self.results("PT-2026-9999"))

    def test_the_live_results_are_for_doctors_only(self):
        self.assertEqual(login(1001, "pat123").get("/search/results/?q=PT-2026").status_code, 403)
        self.assertEqual(Client().get("/search/results/?q=PT-2026").status_code, 403)

    def test_the_script_asks_after_two_characters_clears_with_the_round_button_and_refocuses(self):
        script = (Path(__file__).resolve().parent.parent / "gui" / "static" / "js" / "G_Search.js").read_text(encoding="utf-8")
        for part in ("text.length < 2", "data-results-url", "input.value = ''", "input.focus()", "clear.hidden"):
            self.assertIn(part, script)
        self.assertIn("G_Search.js", self.page())

    def test_the_old_box_markup_is_gone(self):
        page = self.page()
        self.assertNotIn("searchbox", page)
        self.assertNotIn('class="input focus"', page)


class SearchPrivacy(unittest.TestCase):
    """Partial IDs and names only look inside the doctor's own patients. A stranger is found by the whole ID, typed exactly."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.stranger = new_patient(self.s, "Sam Stranger", PASSWORD, "Male", BORN)

    def found(self, query):
        return [link.patient.user_id for link in self.s.find_patients(2001, query)]

    def test_the_whole_id_finds_exactly_that_patient_ignoring_case_and_spaces(self):
        for query in ("PT-2026-01001", "pt-2026-01001", "  PT-2026-01001  ", "PT - 2026 - 01001", "p t-2026-0 1001"):
            self.assertEqual(self.found(query), [1001], query)
        self.assertEqual(self.found(self.stranger.display_id), [self.stranger.user_id])

    def test_a_partial_id_never_lists_a_patient_the_doctor_does_not_have(self):
        for query in ("PT-2026", "PT-2026-0", "PT-2026-0100", "PT-", "2026", "01001", "1001", "PT-2026-0100", "PT-2026-01"):
            self.assertEqual(self.found(query), [], query)

    def test_a_name_or_mobile_number_never_finds_a_stranger(self):
        for query in ("Juan", "Dela Cruz", "Sam", "Stranger", "0917 123 4567", "09171234567", "+63 917 123 4567"):
            self.assertEqual(self.found(query), [], query)

    def test_the_wrong_year_or_a_wrong_number_in_a_whole_looking_id_finds_nothing(self):
        self.assertEqual(self.found("PT-2025-01001"), [])
        self.assertEqual(self.found("PT-2026-99999"), [])
        self.assertEqual(self.found("DR-2026-02001"), [])                              # a doctor's ID is not a patient

    def test_once_a_patient_allows_the_doctor_part_of_the_id_and_the_name_work(self):
        approve(self.s, 2001, 1001)
        for query in ("1001", "PT-2026-0100", "juan", "dela"):
            self.assertEqual(self.found(query), [1001], query)
        self.assertEqual(self.found("sam"), [])                                        # the stranger is still hidden

    def test_a_patient_who_took_access_back_stays_one_of_the_doctors_own_but_a_waiting_or_declined_request_does_not_count(self):
        request = approve(self.s, 2001, 1001)
        self.s.revoke_access(request.request_id, 1001)
        self.assertEqual(self.found("juan"), [1001])                                    # allowed before
        waiting = self.s.request_access(self.s.get_doctor(2001), self.stranger.user_id)
        self.assertEqual(self.found("sam"), [])                                        # asked, not allowed
        self.s.respond_to_request(waiting.request_id, self.stranger.user_id, False)
        self.assertEqual(self.found("sam"), [])                                        # declined

    def test_the_page_follows_the_same_rules(self):
        page = html(self.doc.get("/search/?q=PT-2026-0100"))
        self.assertIn("No patient found", page)
        self.assertNotIn("Juan Dela Cruz", page)
        self.assertIn("Juan Dela Cruz", html(self.doc.get("/search/?q=PT-2026-01001")))
        self.assertIn("No patient found", html(self.doc.get("/search/results/?q=Juan")))


class MarkingMatches(unittest.TestCase):
    def test_every_match_is_marked_and_the_rest_is_escaped(self):
        self.assertEqual(highlight("PT-2026-01001", "PT-2026-0100"), "<mark>PT-2026-0100</mark>1")
        self.assertEqual(highlight("Ana Anaya", "ana"), "<mark>Ana</mark> <mark>Ana</mark>ya")
        self.assertEqual(highlight("A&B <i>", "&b"), "A<mark>&amp;B</mark> &lt;i&gt;")
        self.assertEqual(highlight("Juan", ""), "Juan")
        self.assertEqual(highlight("Juan", "j"), "Juan")                                # one character marks nothing
        self.assertEqual(highlight("Juan", "xyz"), "Juan")


if __name__ == "__main__":
    unittest.main()
