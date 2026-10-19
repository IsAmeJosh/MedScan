"""The doctor's side: how each patient stands with a doctor (PatientLink), the Patients list and its chips, Search,
and the one Patient page with its locked and open states."""
import re
import unittest
from datetime import datetime, timedelta

from models.M_Patient_Link import PatientLink
from tests.helpers import BORN, PASSWORD, approve, count, fresh_system, html, login, new_patient


class ThePatientLinkClass(unittest.TestCase):
    """The model on its own, no database needed."""

    def test_each_kind_has_its_own_pill_word(self):
        words = {kind: PatientLink(None, kind).label for kind in PatientLink.ORDER}
        self.assertEqual(words, {"access": "Allowed", "waiting": "Waiting", "emergency": "Emergency",
                                 "denied": "Declined", "locked": "Locked"})

    def test_access_is_by_qr_only_when_it_came_from_a_scan(self):
        self.assertTrue(PatientLink(None, "access", via="qr").approved_by_qr)
        self.assertFalse(PatientLink(None, "access", via="request").approved_by_qr)
        self.assertFalse(PatientLink(None, "waiting", via="qr").approved_by_qr)

    def test_the_list_order_is_by_kind_then_newest_first(self):
        now = datetime.now()
        lines = [PatientLink("denied", "denied", now), PatientLink("old", "access", now - timedelta(days=2)),
                 PatientLink("wait", "waiting", now), PatientLink("new", "access", now)]
        self.assertEqual([line.patient for line in sorted(lines, key=PatientLink.sort_key)], ["new", "old", "wait", "denied"])


class WorkingOutTheLinks(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def person(self, name):
        return new_patient(self.s, name, PASSWORD, "F", BORN)

    def kind_of(self, patient):
        return self.s.patient_link(2001, patient).kind

    def test_nothing_between_them_is_locked(self):
        self.assertEqual(self.kind_of(self.s.get_patient(1001)), "locked")
        self.assertEqual(self.s.patient_links_for_doctor(2001), [])

    def test_each_state_gets_its_own_kind(self):
        juan = self.s.get_patient(1001)
        request = self.s.request_access(self.reyes, 1001)
        self.assertEqual(self.kind_of(juan), "waiting")
        self.s.respond_to_request(request.request_id, 1001, False)
        self.assertEqual(self.kind_of(juan), "denied")
        again = self.s.request_access(self.reyes, 1001)
        self.s.respond_to_request(again.request_id, 1001, True)
        self.assertEqual(self.kind_of(juan), "access")
        self.s.revoke_access(again.request_id, 1001)
        self.assertEqual(self.kind_of(juan), "denied")

    def test_an_emergency_beats_a_denial_but_an_approval_or_a_waiting_request_beats_an_emergency(self):
        juan = self.s.get_patient(1001)
        request = self.s.request_access(self.reyes, 1001)
        self.s.respond_to_request(request.request_id, 1001, False)
        self.s.emergency_access(self.reyes, 1001, "Collapsed")
        self.assertEqual(self.kind_of(juan), "emergency")
        self.s.request_access(self.reyes, 1001)
        self.assertEqual(self.kind_of(juan), "waiting")
        newest = self.s.request_rows_for_doctor(2001, "Pending")[0][0]
        self.s.respond_to_request(newest.request_id, 1001, True)
        self.assertEqual(self.kind_of(juan), "access")

    def test_an_approval_by_qr_remembers_how_it_happened(self):
        self.s.scan_qr(self.reyes, self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text)
        link = self.s.patient_link(2001, self.s.get_patient(1001))
        self.assertEqual(link.kind, "access")
        self.assertTrue(link.approved_by_qr)

    def test_the_list_has_one_line_per_patient_in_order_and_the_counts_match_the_chips(self):
        yes, wait, no, em = (self.person(n) for n in ("Yes", "Wait", "No", "Em"))
        for patient, answer in [(yes, True), (wait, None), (no, False)]:
            request = self.s.request_access(self.reyes, patient.user_id)
            if answer is not None:
                self.s.respond_to_request(request.request_id, patient.user_id, answer)
        self.s.emergency_access(self.reyes, em.user_id, "Collapsed")
        again = self.s.request_access(self.reyes, no.user_id)                        # a second request: still one line
        links = self.s.patient_links_for_doctor(2001)
        self.assertEqual([(l.patient.name, l.kind) for l in links],
                         [("Yes", "access"), ("No", "waiting"), ("Wait", "waiting"), ("Em", "emergency")])
        self.assertEqual(self.s.link_counts(links), {"all": 4, "access": 1, "waiting": 2, "emergency": 1, "denied": 0})
        self.assertEqual([l.patient.name for l in self.s.filter_links(links, "waiting")], ["No", "Wait"])
        self.assertEqual(len(self.s.filter_links(links, "nonsense")), 4)
        self.assertIsNotNone(again)

    def test_search_finds_anyone_by_id_or_mobile_but_a_name_only_finds_your_own(self):
        found = self.s.find_patients(2001, "1001")
        self.assertEqual([(l.patient.user_id, l.kind) for l in found], [(1001, "locked")])
        self.assertEqual(self.s.find_patients(2001, "0917 123 4567")[0].patient.user_id, 1001)
        self.assertEqual(self.s.find_patients(2001, "juan"), [])                     # not theirs yet
        approve(self.s)
        self.assertEqual([(l.patient.name, l.kind) for l in self.s.find_patients(2001, "juan")], [("Juan Dela Cruz", "access")])

    def test_search_never_lists_a_patient_twice_and_ignores_nonsense(self):
        approve(self.s)
        self.assertEqual(len(self.s.find_patients(2001, "1001")), 1)                 # found by ID and by being theirs
        for text in ("", "   ", None, "zzz", "2001", "9999999"):
            self.assertEqual(self.s.find_patients(2001, text), [], text)

    def test_recent_patients_have_the_time_and_leave_when_access_is_taken_back(self):
        request = approve(self.s)
        self.s.open_record(self.reyes, 1001)
        ((patient, when),) = self.s.recent_patient_rows_for_doctor(2001)
        self.assertEqual(patient.user_id, 1001)
        self.assertLess(abs((datetime.now() - when).total_seconds()), 60)
        self.s.revoke_access(request.request_id, 1001)
        self.assertEqual(self.s.recent_patient_rows_for_doctor(2001), [])


class ThePages(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    @staticmethod
    def main(response):
        return html(response).split('<main class="content')[1].split("</main>")[0]

    def test_patients_can_not_use_the_doctor_pages(self):
        for url in ("/search/", "/search/?q=1001", "/patient/1001/", "/patients/", "/qr/scan/?code=x"):
            r = self.pat.get(url)
            self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/"), url)

    def test_a_patient_that_does_not_exist_goes_home(self):
        self.assertEqual(self.doc.get("/patient/99999/")["Location"], "/dashboard/")

    def test_the_patients_list_says_how_each_line_came_about(self):
        self.s.scan_qr(self.s.get_doctor(2001), self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text)
        em = new_patient(self.s, "Em Patient", PASSWORD, "F", BORN)
        self.doc.post(f"/patient/{em.user_id}/emergency/", {"reason": "Collapsed"})
        page = self.main(self.doc.get("/patients/"))
        self.assertIn("QR scan today", page)
        self.assertIn("emergency, ended today", page)
        self.assertEqual([m for m in re.findall(r'class="pill (green|red)">(Allowed|Emergency)<', page)],
                         [("green", "Allowed"), ("red", "Emergency")])
        self.assertIn("Em Patient", self.main(self.doc.get("/patients/?show=emergency")))
        self.assertNotIn("Em Patient", self.main(self.doc.get("/patients/?show=access")))

    def test_the_open_page_has_the_three_tabs_and_the_note_form(self):
        approve(self.s)
        page = html(self.doc.get("/patient/1001/"))
        for tab in ("notes", "medical", "info"):
            self.assertIn(f'data-pane-tab="{tab}"', page)
            self.assertIn(f'data-pane="{tab}"', page)
        self.assertIn('action="/patient/1001/consult/"', page)
        self.assertIn("Allowed</span>", page)
        self.assertNotIn("Allowed by QR scan", page)
        self.assertNotIn('id="emergency-sheet"', page)

    def test_a_live_scan_lands_on_the_open_page_that_says_how_the_doctor_got_in(self):
        text = self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text
        r = self.doc.get(f"/qr/scan/?code={text}", follow=True)
        page = html(r)
        self.assertEqual(r.redirect_chain[-1][0], "/patient/1001/")
        self.assertIn("Allowed by QR scan", page)
        self.assertIn("Scan successful. Access approved and logged.", page)
        self.assertIn('<div class="allergy">', page)                                   # the allergy alert
        self.assertIn("<b>Allergies</b>", page)
        self.assertEqual(count("tb_record_views"), 1)

    def test_the_emergency_open_page_says_so_and_warns_that_it_was_logged(self):
        self.doc.post("/patient/1001/emergency/", {"reason": "Collapsed"})
        page = html(self.doc.get("/patient/1001/"))
        self.assertIn("Emergency access", page)
        self.assertIn("This was logged and Juan was notified", page)
        self.assertIn('class="pill red">Emergency access<', page)

    def test_the_locked_page_changes_with_the_state_of_the_request(self):
        page = html(self.doc.get("/patient/1001/"))
        self.assertIn("Send access request", page)
        self.assertIn("Scan his QR code", page)                                 # the word comes from the sex on file
        self.doc.post("/request/1001/")
        waiting = html(self.doc.get("/patient/1001/"))
        self.assertIn("Request sent", waiting)
        self.assertNotIn("Send access request", waiting)
        self.assertIn("Your request is with Juan", waiting)

    def test_search_results_open_the_patient_page_and_say_where_things_stand(self):
        page = self.main(self.doc.get("/search/?q=1001"))
        self.assertIn('href="/patient/1001/"', page)
        self.assertIn('<span class="pill grey">Locked</span>', page)
        self.doc.post("/request/1001/")
        self.assertIn('<span class="pill amber">Waiting</span>', self.main(self.doc.get("/search/?q=1001")))
        self.assertIn('value="1001"', html(self.doc.get("/search/?q=1001")))          # the box keeps what was typed

    def test_the_top_bar_and_the_phone_tab_both_lead_to_search(self):
        page = html(self.doc.get("/dashboard/"))
        self.assertIn('<form class="tsearch d-only" method="get" action="/search/"', page)
        self.assertRegex(page, r'<a href="/search/" class="">.*?</svg>Search</a>')
        self.assertRegex(html(self.doc.get("/search/")), r'<a href="/search/" class="on">')

    def test_the_scanner_starts_by_itself_and_has_a_way_to_try_again(self):
        page = html(self.doc.get("/qr/"))
        self.assertIn("Starting the camera", page)
        self.assertIn('id="qr-retry" hidden', page)
        self.assertIn("Recent scans", page)


if __name__ == "__main__":
    unittest.main()
