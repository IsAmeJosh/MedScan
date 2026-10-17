"""The simpler flow: the rules behind the new Home, Patients and Privacy pages, the search box's suggestions,
and the small helpers (relative times, remembering the ID on the login page)."""
import re
import unittest
from datetime import datetime, timedelta

from django.test import Client

from gui.G_Filters import ago
from tests.helpers import (BORN, PASSWORD, approve, execute, fresh_system, html, login, new_patient, rows)


class Doctors(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def patient(self, name, **kw):
        return new_patient(self.s, name, PASSWORD, "F", BORN, **kw)

    def ask(self, patient, answer=None, doctor=None):
        request = self.s.request_access(doctor or self.reyes, patient.user_id)
        if answer is not None:
            self.s.respond_to_request(request.request_id, patient.user_id, answer)
        return request


class ReadyAndRecent(Doctors):
    def test_ready_to_open_means_approved_and_never_opened(self):
        a, b, c = (self.patient(n) for n in ["Ana", "Bea", "Cy"])
        self.ask(a, True)
        self.ask(b, True)
        self.ask(c)   # not answered
        self.assertEqual([p.name for p in self.s.unopened_patients_for_doctor(2001)], ["Ana", "Bea"])
        self.s.open_record(self.reyes, a.user_id)
        self.assertEqual([p.name for p in self.s.unopened_patients_for_doctor(2001)], ["Bea"])

    def test_an_approval_that_was_taken_back_is_not_ready(self):
        ana = self.patient("Ana")
        request = self.ask(ana, True)
        self.s.revoke_access(request.request_id, ana.user_id)
        self.assertEqual(self.s.unopened_patients_for_doctor(2001), [])

    def test_recent_patients_are_newest_first_each_once_and_limited(self):
        people = [self.patient(f"P{n}") for n in range(7)]
        for p in people:
            self.ask(p, True)
            self.s.open_record(self.reyes, p.user_id)
        execute("UPDATE tb_record_views SET created_at = created_at - INTERVAL 20 MINUTE")
        self.s.open_record(self.reyes, people[0].user_id)   # opened again: now the newest
        recent = self.s.recent_patient_rows_for_doctor(2001, limit=5)
        self.assertEqual([p.name for p, _ in recent], ["P0", "P6", "P5", "P4", "P3"])

    def test_recent_leaves_out_patients_who_took_access_back(self):
        ana, bea = self.patient("Ana"), self.patient("Bea")
        ask_ana = self.ask(ana, True)
        self.ask(bea, True)
        self.s.open_record(self.reyes, ana.user_id)
        self.s.open_record(self.reyes, bea.user_id)
        self.s.revoke_access(ask_ana.request_id, ana.user_id)
        self.assertEqual([p.name for p, _ in self.s.recent_patient_rows_for_doctor(2001)], ["Bea"])

    def test_an_emergency_opened_record_is_recent_until_the_hour_is_up(self):
        stranger = self.patient("Stranger")
        self.s.emergency_access(self.reyes, stranger.user_id, "Collapsed")
        self.s.open_record(self.reyes, stranger.user_id)
        self.assertEqual([p.name for p, _ in self.s.recent_patient_rows_for_doctor(2001)], ["Stranger"])
        execute("UPDATE tb_emergency_logs SET created_at = created_at - INTERVAL 61 MINUTE")
        self.assertEqual(self.s.recent_patient_rows_for_doctor(2001), [])


class SearchingMyPatients(Doctors):
    def setUp(self):
        super().setUp()
        self.juan = self.s.get_patient(1001)
        self.maria = self.patient("Maria Santos")
        self.mario = self.patient("Mario Reyes")
        self.stranger = self.patient("Mariano Stranger")
        for p in (self.juan, self.maria, self.mario):
            self.ask(p, True)   # the stranger never approved

    def names(self, text, **kw):
        return [p.name for p in self.s.search_my_patients(2001, text, **kw)]

    def test_by_part_of_a_name_any_case(self):
        self.assertEqual(self.names("mari"), ["Maria Santos", "Mario Reyes"])
        self.assertEqual(self.names("JUAN"), ["Juan Dela Cruz"])
        self.assertEqual(self.names("dela cruz"), ["Juan Dela Cruz"])

    def test_by_the_start_of_an_id_or_a_full_id(self):
        self.assertEqual(self.names("1001"), ["Juan Dela Cruz"])
        self.assertEqual(self.names(str(self.maria.user_id)), ["Maria Santos"])
        everyone = [self.juan, self.maria, self.mario]   # IDs come in order, and all start with 1
        self.assertEqual(self.names("1"), [p.name for p in everyone])
        prefix = str(self.maria.user_id)[:3]
        self.assertEqual(self.names(prefix), [p.name for p in everyone if str(p.user_id).startswith(prefix)])
        self.assertEqual(self.names(self.juan.display_id), ["Juan Dela Cruz"])
        self.assertEqual(self.names(self.juan.display_id.lower()), ["Juan Dela Cruz"])

    def test_never_a_patient_who_has_not_approved_you(self):
        self.assertNotIn("Mariano Stranger", self.names("mari"))
        self.assertEqual(self.names(str(self.stranger.user_id)), [])

    def test_nothing_for_blank_and_a_limit_for_many(self):
        self.assertEqual(self.names(""), [])
        self.assertEqual(self.names("   "), [])
        self.assertEqual(len(self.names("1", limit=2)), 2)

    def test_odd_text_is_harmless(self):
        for text in ["%", "'; DROP TABLE tb_patients; --", "<script>", "\\", "x" * 500]:
            self.assertEqual(self.names(text), [])


class WhatHappenedToMyRecord(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def test_views_and_emergency_uses_are_one_feed_newest_first(self):
        approve(self.s)
        self.s.open_record(self.reyes, 1001)
        execute("UPDATE tb_record_views SET created_at = created_at - INTERVAL 5 MINUTE")
        self.s.emergency_access(self.reyes, 1001, "Collapsed")
        feed = self.s.activity_for_patient(1001)
        self.assertEqual([item["kind"] for item in feed], ["override", "view"])
        self.assertEqual((feed[0]["detail"], feed[0]["doctor"].name), ("Collapsed", "Reyes"))
        self.assertEqual(feed[1]["detail"], "")

    def test_a_record_opened_during_an_emergency_is_marked_as_such(self):
        self.s.emergency_access(self.reyes, 1001, "Collapsed")
        self.s.open_record(self.reyes, 1001)
        self.assertEqual(sorted(item["kind"] for item in self.s.activity_for_patient(1001)), ["emergency_view", "override"])

    def test_nothing_has_happened_yet(self):
        self.assertEqual(self.s.activity_for_patient(1001), [])

    def test_only_my_own_activity(self):
        other = new_patient(self.s, "Other", PASSWORD, "F", BORN)
        self.s.emergency_access(self.reyes, other.user_id, "Collapsed")
        self.assertEqual(self.s.activity_for_patient(1001), [])


class RequestsAndNotifications(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def test_pending_request_ids(self):
        first = self.s.request_access(self.reyes, 1001)
        self.assertEqual(self.s.pending_request_ids_for_patient(1001), {first.request_id})
        self.s.respond_to_request(first.request_id, 1001, True)
        self.assertEqual(self.s.pending_request_ids_for_patient(1001), set())
        self.assertEqual(self.s.pending_request_ids_for_patient(2001), set())

    def test_the_request_behind_a_notification(self):
        request = self.s.request_access(self.reyes, 1001)
        (note,) = self.s.inbox(1001)
        behind = self.s.request_behind(note)
        self.assertEqual((behind.request_id, behind.status), (request.request_id, "Pending"))
        self.s.emergency_access(self.reyes, 1001, "x")
        emergency = [n for n in self.s.inbox(1001) if "emergency" in n.message][0]
        self.assertIsNone(self.s.request_behind(emergency))

    def test_answering_marks_only_that_requests_notifications_read(self):
        other_doctor = self.s.register_doctor("Cruz", PASSWORD, "ENT")
        first = self.s.request_access(self.reyes, 1001)
        self.s.request_access(other_doctor, 1001)
        self.s.respond_to_request(first.request_id, 1001, True)
        unread = [n.message for n in self.s.inbox(1001) if not n.is_read]
        self.assertEqual(unread, ["Dr. Cruz requests access to your record."])


class SuggestionsEndpoint(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def ask(self, text, client=None):
        return (client or self.doc).get("/patients/suggest/", {"q": text})

    def test_it_returns_my_patients_with_a_link_to_the_record(self):
        approve(self.s)
        data = self.ask("jua").json()
        self.assertEqual(data["ok"], True)
        (item,) = data["items"]
        self.assertEqual(item["name"], "Juan Dela Cruz")
        self.assertEqual(item["url"], "/patient/1001/")
        self.assertTrue(item["id"].startswith("PT-"))

    def test_nothing_before_the_patient_approves(self):
        self.assertEqual(self.ask("juan").json(), {"ok": True, "items": []})

    def test_never_another_doctors_patient(self):
        other = self.s.register_doctor("Cruz", PASSWORD, "ENT")
        request = self.s.request_access(other, 1001)
        self.s.respond_to_request(request.request_id, 1001, True)
        self.assertEqual(self.ask("juan").json()["items"], [])   # Juan approved Dr. Cruz, not Dr. Reyes

    def test_blank_and_odd_text(self):
        for text in ["", "   ", "%", "' OR 1=1 --", "x" * 400]:
            r = self.ask(text)
            self.assertEqual((r.status_code, r.json()["items"]), (200, []), text)

    def test_patients_and_strangers_are_refused(self):
        for client in [self.pat, Client()]:
            r = self.ask("juan", client)
            self.assertEqual((r.status_code, r.json()), (403, {"ok": False}))

    def test_names_are_escaped_by_json_and_never_become_markup(self):
        approve(self.s)
        execute("UPDATE tb_patients SET name = '<b>Juan</b>' WHERE patient_id = 1001")
        self.assertEqual(self.ask("juan").json()["items"][0]["name"], "<b>Juan</b>")   # plain text: the script adds it as text

    def test_typing_does_not_count_as_activity(self):
        client = Client()
        client.post("/", {"user_id": "2001", "password": "doc123"})
        self.assertNotIn("sessionid", client.get("/patients/suggest/?q=a").cookies)


class RelativeTimes(unittest.TestCase):
    def test_how_people_say_it(self):
        now = datetime.now()
        for delta, expected in [(timedelta(seconds=5), "just now"), (timedelta(seconds=59), "just now"),
                                (timedelta(minutes=1, seconds=5), "1 min ago"), (timedelta(minutes=45), "45 min ago"),
                                (timedelta(hours=3, minutes=10), "3 h ago"), (timedelta(hours=30), "yesterday")]:
            self.assertEqual(ago(now - delta), expected, delta)

    def test_older_ones_show_the_date(self):
        old = datetime.now() - timedelta(days=10)
        self.assertEqual(ago(old), old.strftime("%b ") + str(old.day) + old.strftime(", %Y"))

    def test_anything_else_is_left_alone(self):
        self.assertEqual(ago("not a date"), "not a date")
        self.assertIsNone(ago(None))

    def test_notifications_show_how_long_ago_with_the_exact_time_on_hover(self):
        s = fresh_system(self)
        s.request_access(s.get_doctor(2001), 1001)
        page = html(login(1001, "pat123").get("/dashboard/"))
        self.assertRegex(page, r'<div class="s" title="[A-Z][a-z]{2} \d\d, \d{4} \d\d:\d\d">Today, \d\d:\d\d &middot; Opens Access')


class LoginRemembersTheId(unittest.TestCase):
    def test_the_box_and_the_hooks(self):
        page = html(Client().get("/"))
        field = re.search(r'<input[^>]*name="user_id"[^>]*>', page).group(0)
        self.assertIn('data-remember="medscan_login_id"', field)
        self.assertIn('data-remember-box="remember"', field)
        self.assertRegex(page, r'<input type="checkbox" id="remember"> Remember me')

    def test_the_boxes_start_empty_with_no_hints_and_errors_come_only_after_pressing_log_in(self):
        page = html(Client().get("/"))
        for name in ("user_id", "password"):
            tag = re.search(r'<input[^>]*name="%s"[^>]*>' % name, page).group(0)
            self.assertNotIn("placeholder", tag)
            self.assertNotIn("data-hint", tag)
            self.assertIn('data-quiet="1"', tag)
        self.assertIn('data-validate="login-id"', page)
        self.assertIn('data-validate="login-password"', page)
        self.assertIn("data-validate-form", page)

    def test_the_logout_question_is_a_modal_over_the_profile_page(self):
        page = html(login(1001, "pat123").get("/logout/"))
        self.assertIn('<div class="scrim"', page)
        self.assertIn('<div class="modal">', page)
        self.assertIn("Log out of MedScan?", page)
        self.assertIn("You will need your ID and password to log in again.", page)
        self.assertIn("Juan Dela Cruz", page.split('<div class="scrim"')[0])          # the Profile page is behind it
        self.assertRegex(page, r'(?s)<form method="post" action="/logout/">.*Log out</button>')
        self.assertIn('href="/profile/">Stay</a>', page)

    def test_logging_out_ends_the_session(self):
        client = login(1001, "pat123")
        r = client.post("/logout/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/"))
        self.assertEqual(client.get("/dashboard/")["Location"], "/")
        self.assertEqual(Client().get("/logout/")["Location"], "/")                  # nobody logged in: just the login page

    def test_the_password_is_never_part_of_it(self):
        page = html(Client().get("/"))
        self.assertNotIn("data-remember", re.search(r'<input[^>]*name="password"[^>]*>', page).group(0))


class ThePageFrame(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def test_doctors_get_the_search_scripts_and_patients_do_not(self):
        doctor = html(self.doc.get("/dashboard/"))
        patient = html(self.pat.get("/dashboard/"))
        self.assertIn("G_Suggest.js", doctor)
        self.assertNotIn("G_Suggest.js", patient)
        self.assertNotIn("G_Emergency.js", doctor)           # the emergency question is a sheet on the locked patient page now
        for script in ["G_Shell.js", "G_Idle.js", "G_Dialogs.js"]:
            self.assertIn(script, doctor)
            self.assertIn(script, patient)

    def test_the_top_bar_has_the_search_box_with_its_shortcut_hint_and_suggestion_area(self):
        page = html(self.doc.get("/dashboard/"))
        self.assertIn('data-suggest-url="/patients/suggest/"', page)
        self.assertIn('<kbd title="Press / to search">/</kbd>', page)
        self.assertIn('id="suggest" hidden', page)
        self.assertNotIn("top-search", html(self.pat.get("/dashboard/")))

    def test_there_are_no_breadcrumbs_and_no_date_in_the_top_bar(self):
        for client in (self.doc, self.pat):
            page = html(client.get("/dashboard/"))
            self.assertNotIn('class="crumbs"', page)
            self.assertNotIn("top-date", page)

    def test_every_script_the_pages_load_exists(self):
        from pathlib import Path
        static = Path(__file__).resolve().parent.parent / "gui" / "static"
        for client in (self.doc, self.pat):
            for path in re.findall(r'src="/static/([^"?]+)', html(client.get("/dashboard/"))):
                self.assertTrue((static / path).exists(), path)


class SignUpAndHomeScreens(unittest.TestCase):
    """The sign-up and home screens: one sign-up form with a Patient / Doctor switch, and the search dim."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def test_signing_up_is_one_form_with_a_patient_doctor_switch_and_starts_as_a_patient(self):
        page = html(Client().get("/register/"))
        self.assertEqual(page.count("<form"), 1)
        self.assertIn('<div class="seg">', page)
        self.assertIn('<a href="?role=patient" class="on">Patient</a>', page)
        self.assertIn('<a href="?role=doctor" class="">Doctor</a>', page)
        self.assertIn('name="role" value="Patient"', page)

    def test_each_role_gets_its_own_short_form(self):
        patient = html(Client().get("/register/?role=patient"))
        doctor = html(Client().get("/register/?role=doctor"))
        self.assertIn('name="role" value="Patient"', patient)
        self.assertIn('name="role" value="Doctor"', doctor)
        for field in ("contact_number", "date_of_birth", "sex", "password", "name"):
            self.assertIn(f'name="{field}"', patient)
        for field in ("specialty", "clinic", "password", "name"):
            self.assertIn(f'name="{field}"', doctor)
        for field in ("specialty", "clinic"):
            self.assertNotIn(f'name="{field}"', patient)
        for field in ("date_of_birth", "allergies"):
            self.assertNotIn(f'name="{field}"', doctor)
        self.assertIn('name="contact_number"', doctor)                      # optional for a doctor
        self.assertNotIn("required", re.search(r'<input[^>]*name="contact_number"[^>]*>', doctor).group(0))

    def test_medical_history_is_a_collapsed_optional_section(self):
        page = html(Client().get("/register/?role=patient"))
        self.assertRegex(page, r'<details class="more" >')          # closed
        self.assertIn("Add medical history now (optional)", page)
        self.assertIn('name="allergies"', page)

    def test_a_form_with_a_mistake_stays_on_the_same_role_and_keeps_the_typing(self):
        r = Client().post("/register/", {"role": "Doctor", "name": "Dr Who", "password": "abc", "specialty": "ENT"})
        page = html(r)
        self.assertIn('name="role" value="Doctor"', page)
        self.assertIn('value="Dr Who"', page)
        self.assertIn("Password must be", page)

    def test_an_unknown_role_in_the_address_shows_the_patient_form(self):
        page = html(Client().get("/register/?role=admin"))
        self.assertIn('name="role" value="Patient"', page)
        self.assertIn('name="date_of_birth"', page)

    def test_home_has_no_finish_your_profile_card_any_more(self):
        """Home has the ID card, the waiting requests and the recent activity."""
        self.assertNotIn("Finish your health profile", html(self.pat.get("/dashboard/")))

    def test_an_empty_allergy_list_says_none_recorded_not_no_known_allergies(self):
        bare = new_patient(self.s, "Bare", PASSWORD, "F", BORN)
        approve(self.s, 2001, bare.user_id)
        mine = login(bare.user_id, PASSWORD)
        pages = [html(mine.get("/dashboard/")), html(mine.get("/record/")), html(self.doc.get(f"/patient/{bare.user_id}/"))]
        for page in pages:
            self.assertNotIn("No known allergies", page)
        self.assertIn("None recorded", pages[1])      # My Record
        self.assertIn("None recorded", pages[2])      # the doctor's page

    def test_the_doctor_home_has_the_two_panels_of_the_design(self):
        page = html(self.doc.get("/dashboard/"))
        for heading in ("Recent patients", "Waiting on patients"):
            self.assertIn(f"</svg>{heading}</h2>", page)
        self.assertNotIn("stat2", page)

    def test_the_patients_page_is_one_list_with_a_pill_and_a_chevron_on_every_line(self):
        approve(self.s)
        page = html(self.doc.get("/patients/"))
        line = re.search(r'<a class="row" href="/patient/1001/">.*?</a>', page, re.S).group(0)
        self.assertIn("Juan Dela Cruz", line)
        self.assertIn("PT-2026-01001 &middot; Male", line)
        self.assertIn('<span class="pill green">Access</span>', line)
        self.assertIn("approved today", line)
        for chip in ("All", "With access", "Waiting", "Emergency", "Denied"):
            self.assertIn(f"{chip} <em>", page)

    def test_the_locked_page_offers_scan_request_and_emergency_in_that_order(self):
        page = html(self.doc.get("/patient/1001/"))
        scan, send, emergency = (page.index(text) for text in ("QR code</a>", "Send access request", "Emergency access"))
        self.assertTrue(scan < send < emergency)

    def test_the_search_box_stays_sharp_while_the_rest_of_the_page_is_dimmed_and_blurred(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "gui"
        css = (root / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"body\.searching \.side, body\.searching \.content, body\.searching \.top > :not\(\.tsearch\) \{ filter:blur\(")
        self.assertIn("body.searching .top {", css)                      # the bar's own background is dimmed too
        self.assertNotIn("search-scrim", html(self.doc.get("/dashboard/")))   # no separate layer is needed any more
        script = (root / "static" / "js" / "G_Suggest.js").read_text(encoding="utf-8")
        self.assertIn("'focus'", script)
        self.assertIn("searching", script)

    def test_a_helper_class_never_reuses_the_name_of_a_page_part(self):
        # ".row.top" once picked up the top bar's height and clipped the welcome card
        from pathlib import Path
        folder = Path(__file__).resolve().parent.parent / "gui"
        for path in (folder / "templates").glob("*.html"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r'class="[^"]*row top', path.name)
        css = (folder / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")
        self.assertNotIn(".row.top", css)

    def test_the_templates_use_no_inline_styles_except_the_bar_heights_and_progress(self):
        from pathlib import Path
        folder = Path(__file__).resolve().parent.parent / "gui" / "templates"
        for path in folder.glob("*.html"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if 'style="' in line:
                    self.assertTrue("height:{{" in line or "width:{{" in line, f"{path.name}: {line.strip()}")


class QrCodePage(unittest.TestCase):
    """Only patients have a code. A doctor scans one with the camera or a photo (tests/test_qr_code.py has the rest)."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def test_each_role_has_it_as_its_own_menu_item_with_its_own_name(self):
        self.assertIn("Show my QR code</a>", html(self.pat.get("/dashboard/")))
        self.assertIn("Scan QR code</a>", html(self.doc.get("/dashboard/")))

    def test_you_must_be_logged_in(self):
        self.assertEqual(Client().get("/qr/").status_code, 302)

    def test_a_patient_sees_their_own_code_as_a_sheet_and_nothing_to_scan(self):
        r = self.pat.get("/qr/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/?sheet=qr"))
        page = html(self.pat.get("/dashboard/"))
        sheet = re.search(r'<dialog id="qr-sheet".*?</dialog>', page, re.S).group(0)
        self.assertIn('class="qrbox"', sheet)
        self.assertIn("PT-2026-01001", sheet)
        self.assertNotIn('class="camera"', page)
        self.assertNotIn('id="qr-sheet"', html(self.doc.get("/dashboard/")))      # doctors have no code

    def test_a_doctor_sees_only_the_scanner_and_has_no_code_of_their_own(self):
        page = html(self.doc.get("/qr/"))
        self.assertIn('class="cam"', page)
        self.assertNotIn('class="qrbox"', page)
        self.assertNotIn("DR-2026-02001", page.split('<main class="content')[1])   # no code, no ID card here
        self.assertNotIn('id="qr-sheet"', page)
        for gone in ("Upload a photo", 'id="qr-file"', 'name="q"', "Type the ID"):   # camera only: no upload, no typing
            self.assertNotIn(gone, page.split('<main class="content')[1].split("</main>")[0])

    def test_there_is_no_type_the_id_option_beside_the_scanner(self):
        page = html(self.doc.get("/qr/"))
        self.assertNotIn("Type the ID", page)
        self.assertNotIn('name="q"', page.split('<main class="content')[1])

    def test_the_words_speak_to_the_user_not_to_a_reviewer(self):
        for client in (self.pat, self.doc):
            page = html(client.get("/qr/", follow=True)).split('<main class="content')[1].split('<div class="toasts"')[0]
            for jargon in ("will work", "Preview", "Coming soon", "not a real", "laceholder"):
                self.assertNotIn(jargon, page)
        self.assertIn("When they scan it, they can open your record right away and it is logged.", html(self.pat.get("/dashboard/")))
        self.assertIn("Ask the patient to tap", html(self.doc.get("/qr/")))
        self.assertIn("Their record opens right away. The scan counts as their approval.", html(self.doc.get("/qr/")))

    def test_the_old_tab_address_still_works(self):
        self.assertEqual(self.pat.get("/qr/?tab=scan").status_code, 302)      # a patient's code is a sheet now
        self.assertEqual(self.doc.get("/qr/?tab=show").status_code, 200)

    def test_the_picture_depends_on_the_id_and_is_always_the_same_for_one_id(self):
        from models.M_QR_Code import QRCode
        self.assertEqual(QRCode("PT-2026-01001").svg(), QRCode("PT-2026-01001").svg())
        self.assertNotEqual(QRCode("PT-2026-01001").svg(), QRCode("PT-2026-01002").svg())

    def test_the_code_never_carries_health_information(self):
        page = html(self.pat.get("/dashboard/"))
        page = re.search(r'<dialog id="qr-sheet".*?</dialog>', page, re.S).group(0)
        for secret in ("Penicillin", "Appendectomy", "O+", "09171234567"):
            self.assertNotIn(secret, page)


class FrameAndBubbles(unittest.TestCase):
    """The page frame: labelled menu sections, the user card, boxed page headers and one kind of red number bubble."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def css(self):
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")

    def test_the_menu_has_an_account_section_for_each_role(self):
        for client in (self.doc, self.pat):
            self.assertEqual(re.findall(r'class="nav-label">([A-Za-z]+)<', html(client.get("/dashboard/"))), ["Account"])

    def test_the_name_and_id_at_the_bottom_of_the_sidebar_open_the_profile_where_log_out_lives(self):
        page = html(self.pat.get("/dashboard/"))
        foot = page.split('class="side-foot"')[1].split("</aside>")[0]
        self.assertIn('href="/profile/"', page.split('class="side-foot"')[0][-40:] + foot)
        self.assertIn("PT-2026-01001", foot)
        self.assertNotRegex(page, r"Log out\s*</a>")                      # no log out button on the other pages
        self.assertRegex(html(self.pat.get("/profile/")), r'href="/logout/">.*Log out\s*</a>')

    def test_the_sidebar_numbers_and_the_bell_are_red_bubbles(self):
        css = self.css()
        self.assertIn(".nav a .count{", css)
        self.assertIn(".ibtn .badge {", css)
        self.assertNotIn(".count.red", css)
        for client in (self.doc, self.pat):
            page = html(client.get("/dashboard/"))
            self.assertNotIn('class="count red"', page)
            self.assertIn('class="count"', page)
            self.assertIn('class="badge"', page)

    def test_the_bubbles_are_small_red_dots_without_a_drawn_number(self):
        import re as _re
        rule = _re.search(r"\.ibtn \.badge \{([^}]*)\}", self.css()).group(1)
        self.assertRegex(rule, r"width:8px; height:8px")
        self.assertIn("font-size:0", rule)                  # the number stays in the page for screen readers, but is not drawn
        self.assertIn("var(--red)", rule)

    def test_an_open_record_warns_about_allergies_and_a_locked_one_shows_none(self):
        page = html(self.doc.get("/patient/1001/"))
        self.assertNotIn("Penicillin", page)                                   # locked: nothing leaks
        approve(self.s)
        page = html(self.doc.get("/patient/1001/"))
        self.assertIn("Check before prescribing", page)                        # the red alert under the name
        self.assertIn('class="alert red top-gap"', page)
        self.assertIn('data-pane="medical"', page)                             # and the Medical tab lists them

    def test_the_page_sits_in_the_middle_of_the_screen(self):
        self.assertRegex(self.css(), r"\.content\{padding:[^}]*max-width:\d+px")

    def test_patients_counts_each_chip_and_access_shows_how_many_requests_are_waiting(self):
        approve(self.s)
        patients = html(self.doc.get("/patients/"))
        self.assertRegex(patients, r"All <em>1</em>")
        self.assertRegex(patients, r"With access <em>1</em>")
        self.assertNotIn('class="badge">', html(self.pat.get("/access/?tab=doctors")))          # nothing is waiting
        self.s.request_access(self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview"), 1001)
        self.assertIn('Requests<span class="badge">1</span>', html(self.pat.get("/access/?tab=doctors")))
class AssetAddresses(unittest.TestCase):
    """The page links its styles and scripts with the file's last-changed time, so browsers never keep an old copy."""

    def test_every_style_and_script_link_carries_the_files_change_time(self):
        page = html(Client().get("/"))
        links = re.findall(r'(?:href|src)="(/static/[^"]+)"', page)
        self.assertGreaterEqual(len(links), 5)
        for link in links:
            self.assertRegex(link, r"\?v=\d{9,}$", link)

    def test_the_address_changes_when_the_file_changes(self):
        import os
        import tempfile
        from gui.G_Filters import asset
        from django.contrib.staticfiles import finders
        before = asset("css/G_Style.css")
        path = finders.find("css/G_Style.css")
        original = os.path.getmtime(path)
        try:
            os.utime(path, (original + 100, original + 100))
            self.assertNotEqual(before, asset("css/G_Style.css"))
        finally:
            os.utime(path, (original, original))
        self.assertEqual(before, asset("css/G_Style.css"))


if __name__ == "__main__":
    unittest.main()
