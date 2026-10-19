"""The simpler flow: the rules behind the new Home, Patients and Privacy pages, the search box's suggestions,
and the small helpers (relative times, remembering the ID on the login page)."""
import re
import unittest
from pathlib import Path
from datetime import datetime, timedelta

from django.test import Client

from gui.G_Filters import ago
from tests.helpers import (BORN, PASSWORD, approve, count, execute, fresh_system, html, login, new_patient, rows)


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


class LoginPage(unittest.TestCase):
    def test_there_is_no_remember_me_box(self):
        page = html(Client().get("/"))
        field = re.search(r'<input[^>]*name="user_id"[^>]*>', page).group(0)
        self.assertNotIn("data-remember", field)
        self.assertNotIn("Remember me", page)
        self.assertNotIn('id="remember"', page)

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

    def test_the_logout_question_is_a_modal_over_the_settings_page(self):
        page = html(login(1001, "pat123").get("/logout/"))
        self.assertIn('<div class="scrim"', page)
        self.assertIn('<div class="modal">', page)
        self.assertIn("Log out of MedScan?", page)
        self.assertIn("You will need your ID and password to log in again.", page)
        self.assertIn("Choose how MedScan works for you.", page.split('<div class="scrim"')[0])   # the Settings page is behind it
        self.assertRegex(page, r'(?s)<form method="post" action="/logout/">.*Log out</button>')
        self.assertIn('href="/settings/">Stay</a>', page)

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
        for heading in ("Today", "Recent notes"):
            self.assertIn(f"<h2>{heading}</h2>", page)
        self.assertNotIn("stat2", page)

    def test_the_patients_page_is_one_list_with_a_pill_and_a_chevron_on_every_line(self):
        approve(self.s)
        page = html(self.doc.get("/patients/"))
        line = re.search(r'<a class="row" href="/patient/1001/">.*?</a>', page, re.S).group(0)
        self.assertIn("Juan Dela Cruz", line)
        self.assertIn("PT-2026-01001 &middot; Male", line)
        self.assertIn('<span class="pill green">Allowed</span>', line)
        self.assertIn("allowed today", line)
        for chip in ("All", "Can see", "Waiting", "Emergency", "Declined"):
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
        self.assertIn("Their record opens right away. Showing you the code counts as their OK.", html(self.doc.get("/qr/")))

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

    def test_the_menu_has_profile_then_settings_and_no_account_label_for_each_role(self):
        for client in (self.doc, self.pat):
            page = html(client.get("/dashboard/"))
            self.assertNotIn("nav-label", page)
            self.assertRegex(page, r'(?s)href="/profile/" class="">.*?Profile</a>\s*<a href="/settings/" class="">.*?Settings</a>')
            self.assertIn('class="ibtn gear"', page)                      # the gear, shown on a phone only (the style decides)

    def test_the_name_and_id_at_the_bottom_of_the_sidebar_open_the_profile_and_log_out_lives_in_settings(self):
        page = html(self.pat.get("/dashboard/"))
        foot = page.split('class="side-foot"')[1].split("</aside>")[0]
        self.assertIn('href="/profile/"', page.split('class="side-foot"')[0][-40:] + foot)
        self.assertIn("PT-2026-01001", foot)
        self.assertNotRegex(page, r"Log out\s*</a>")                      # no log out button on the other pages
        self.assertNotIn("/logout/", html(self.pat.get("/profile/")).split('<main class="content">')[1].split("</main>")[0])   # nor on Profile
        self.assertRegex(html(self.pat.get("/settings/")), r'class="act-row danger" href="/logout/">.*Log out')

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
        self.assertRegex(page, r'<div class="allergy">.*<b>Allergies</b><small>Penicillin')   # the red banner under the header
        self.assertIn('data-pane="medical"', page)                             # and the Medical tab lists them

    def test_the_page_sits_in_the_middle_of_the_screen(self):
        self.assertRegex(self.css(), r"\.content\{padding:[^}]*max-width:\d+px")

    def test_patients_counts_each_chip_and_access_shows_how_many_requests_are_waiting(self):
        approve(self.s)
        patients = html(self.doc.get("/patients/"))
        self.assertRegex(patients, r"All <em>1</em>")
        self.assertRegex(patients, r"Can see <em>1</em>")
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


class PatientHomeRefinement(unittest.TestCase):
    """Patient Home: equal Decline and Allow, a care team, recent activity, and emergency access that shows when it ended."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def test_decline_and_allow_look_identical_and_neither_has_an_icon_or_a_colour_of_its_own(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        page = html(self.pat.get("/dashboard/"))
        card = page.split('class="card ask side-ask"')[1]
        self.assertIn('class="btn equal">Decline</button>', card)
        self.assertIn('class="btn equal" data-sheet="review-', card)
        self.assertNotIn("btn danger", card)                              # Decline is not styled as a warning
        self.assertNotIn("btn primary", card.split("<dialog")[0])         # and Allow is not the highlighted choice

    def test_the_review_sheet_has_the_same_two_equal_buttons(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        sheet = html(self.pat.get("/dashboard/")).split("<dialog")[1].split("</dialog>")[0]
        self.assertEqual(sheet.count("btn equal lg"), 2)
        self.assertIn("Dr. Reyes is asking to see your record. If you allow, they can see:", sheet)
        for row in ("Basic info", "Medical", "Care history", "Notes"):
            self.assertIn(f"<span>{row}</span>", sheet)

    def test_the_request_card_has_the_request_time_in_the_corner_and_no_count_pill(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        card = html(self.pat.get("/dashboard/")).split('class="card ask side-ask"')[1]
        self.assertRegex(card, r'<span class="when">Today, \d\d:\d\d</span>')
        self.assertNotIn("waiting</span>", card.split("</div>")[0])

    def test_row_two_has_your_care_team_and_recent_activity_each_in_its_own_panel(self):
        approve(self.s)
        page = html(self.pat.get("/dashboard/"))
        main = page.split('<main class="content">')[1]
        second_row = main.split('<div class="grid">')[2]
        team, activity = second_row.split('<div class="panel">')[1:3]
        self.assertIn("Your care team", team)
        self.assertIn("Recent activity", activity)
        self.assertIn("Dr. Reyes", team)
        self.assertIn("General Medicine", team)
        self.assertIn("Bayanihan Family Clinic", team)
        self.assertIn('href="/record/?tab=care"', team)                   # "Care history" leads to the care history tab
        self.assertEqual(second_row.count('class="panel"'), 2)
        self.assertLess(main.index("Needs your answer"), main.index("Your care team"))   # row one comes before row two

    def test_with_nothing_waiting_the_request_card_says_you_are_all_caught_up(self):
        card = html(self.pat.get("/dashboard/")).split('class="card ask side-ask"')[1].split("</section>")[0]
        self.assertIn('<div class="row empty">', card)
        self.assertIn("<b>You're all caught up</b>", card)
        self.assertIn("New requests from doctors will show up here.", card)
        self.assertNotIn("ask-btns", card)
        self.assertNotIn('class="when"', card)

    def test_the_id_card_comes_first_and_the_request_card_beside_it(self):
        main = html(self.pat.get("/dashboard/")).split('<main class="content">')[1]
        self.assertLess(main.index('class="idcard"'), main.index('class="card ask side-ask"'))
        self.assertEqual(main.split('<div class="grid">')[1].count('<div class="col">'), 2)

    def test_with_no_doctor_yet_the_care_team_says_how_to_get_one(self):
        self.assertIn("No doctor can open your record yet", html(self.pat.get("/dashboard/")))

    def test_an_emergency_opening_shows_when_it_ended(self):
        from datetime import timedelta
        self.s.emergency_access(self.s.get_doctor(2001), 1001, "Unconscious on arrival")
        item = [i for i in self.s.activity_for_patient(1001) if i["kind"] == "override"][0]
        self.assertEqual(item["ended"] - item["when"], timedelta(hours=self.s.EMERGENCY_HOURS))
        page = html(self.pat.get("/access/?tab=history"))
        self.assertRegex(page, r"to \d\d:\d\d")
        self.assertIn("Reason: Unconscious on arrival", page)

    def test_other_history_items_have_no_end_time(self):
        approve(self.s)
        self.s.open_record(self.s.get_doctor(2001), 1001)
        self.assertTrue(all(i["ended"] is None for i in self.s.activity_for_patient(1001)))

    def test_a_declined_request_is_a_quiet_grey_declined_pill_for_the_doctor(self):
        request = self.s.request_access(self.s.get_doctor(2001), 1001)
        self.s.respond_to_request(request.request_id, 1001, False)
        page = html(self.doc.get("/patients/"))
        self.assertIn('<span class="pill declined">Declined</span>', page)
        self.assertNotIn("Denied", page)


class CareHistoryPlaceholders(unittest.TestCase):
    """The care history is hard-coded sample data for the demo: no tables, no saving, clearly marked."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")
        approve(self.s)

    def test_my_record_has_four_tabs_with_care_history_second(self):
        page = html(self.pat.get("/record/"))
        tabs = re.findall(r'data-pane-tab="(\w+)">([A-Za-z ]+)</a>', page)
        self.assertEqual(tabs, [("notes", "Notes"), ("care", "Care history"), ("medical", "Medical"), ("info", "Info")])
        self.assertIn('<div class="utabs">', page)                        # underline tabs, shown on every screen size, not only on a phone

    def test_the_patient_sees_all_six_entries_including_the_one_hidden_from_doctors(self):
        pane = html(self.pat.get("/record/")).split('data-pane="care"')[1].split('data-pane="medical"')[0]
        self.assertIn("<b>Consultation: Dr. Maria Reyes</b>", pane)
        self.assertIn("<b>Admitted: Pneumonia</b>", pane)
        self.assertIn("<b>ER visit: Penicillin reaction</b>", pane)
        self.assertIn("<b>Surgery: Appendectomy</b>", pane)
        self.assertIn("Hidden from doctors", pane)
        self.assertIn("Only you can see this", pane)
        self.assertIn("Places you've been treated", pane)
        self.assertEqual(re.findall(r'<span class="more"', pane).__len__(), 3)   # the hide menu is on the three entries that can be hidden

    def test_the_samples_belong_to_demo_patient_1001_and_everyone_else_reads_not_recorded(self):
        client = Client()
        client.post("/register/", {"role": "Patient", "name": "Zed", "password": PASSWORD, "date_of_birth": BORN,
                                   "contact_number": "0917 000 5555"})
        page = html(client.get("/record/"))
        care = page.split('data-pane="care"')[1].split('data-pane="medical"')[0]
        self.assertIn("Not recorded", care)
        for sample in ("Northview", "Maria Reyes", "Hidden from doctors"):
            self.assertNotIn(sample, care)
        medical = page.split('data-pane="medical"')[1].split('data-pane="info"')[0]
        for sample in ("Hypertension", "Flu shot", "COVID-19 booster", "Since 2024"):
            self.assertNotIn(sample, medical)
        self.assertNotIn("Amlodipine", page.split('data-pane="notes"')[1].split('data-pane="care"')[0])
        self.assertNotIn("Sample data", html(self.pat.get("/record/")))      # the design has no such tag

    def test_the_doctor_never_sees_the_hidden_entry_only_that_one_is_hidden(self):
        page = html(self.doc.get("/patient/1001/"))
        pane = page.split('data-pane="care"')[1].split('data-pane="medical"')[0]
        self.assertNotIn("Private clinic", page)
        self.assertNotIn("Only you can see this", page)
        self.assertNotIn("Hide from doctors", pane)                       # no hide menu for a doctor
        self.assertIn("<b>Admitted: Pneumonia</b>", pane)
        self.assertIn("1 entry hidden by the patient", page)             # the doctor only learns that one entry is hidden

    def test_the_doctors_page_has_a_care_history_tab_and_seen_elsewhere_under_at_a_glance(self):
        page = html(self.doc.get("/patient/1001/"))
        tabs = re.findall(r'data-pane-tab="(\w+)">', page)
        self.assertEqual(tabs, ["notes", "care", "medical", "info"])
        glance = page.split("At a glance")[1]
        self.assertLess(glance.index("Seen elsewhere"), glance.index("1 entry hidden by the patient"))
        self.assertIn("Mabini General Hospital", glance)

    def test_both_placeholder_files_say_so_in_a_comment_and_nothing_is_saved(self):
        from pathlib import Path
        folder = Path(__file__).resolve().parent.parent / "gui" / "templates"
        for name in ("G_Care_History.html", "G_Seen_Elsewhere.html"):
            self.assertIn("demo placeholder", (folder / name).read_text(encoding="utf-8"), name)
        before = count("tb_consultations")
        self.pat.get("/record/")
        self.doc.get("/patient/1001/")
        self.assertEqual(count("tb_consultations"), before)               # looking at it writes nothing

    def test_the_record_pages_open_on_the_tab_named_in_the_address(self):
        from pathlib import Path
        script = (Path(__file__).resolve().parent.parent / "gui" / "static" / "js" / "G_Sheets.js").read_text(encoding="utf-8")
        self.assertIn("[?&]tab=", script)
        self.assertEqual(self.pat.get("/record/?tab=care").status_code, 200)
        self.assertEqual(self.doc.get("/patient/1001/?tab=care").status_code, 200)

    def test_the_new_icons_are_the_designs_own(self):
        from gui.G_Icons import ICONS
        for name in ("stethoscope", "bed", "hidden", "hospital", "download"):
            self.assertIn(name, ICONS)
            self.assertTrue(ICONS[name].startswith("<"))


class ShellAndSettings(unittest.TestCase):
    """Settings for both roles, the shared page header, underline tabs, and the doctor's patient page as the design draws it."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def test_settings_needs_a_login(self):
        self.assertEqual(Client().get("/settings/")["Location"], "/")

    def test_the_patient_settings_have_the_designs_sections_and_rows_in_order(self):
        page = html(self.pat.get("/settings/"))
        self.assertIn("<h1>Settings</h1>", page)
        self.assertIn("Choose how MedScan works for you.", page)
        heads = re.findall(r'class="sec-h"><h2>([A-Za-z ]+)</h2>', page)
        self.assertEqual(heads, ["Notifications", "Display", "Account", "Privacy"])   # Notifications + Display, then Account + Privacy
        for row in ("Access requests", "Record opened", "Hidden care history",
                    "Download my MedScan ID", "Change password", "Text size", "Language"):
            self.assertIn(f"<b>{row}</b>", page, row)
        self.assertNotIn("Let doctors find me by ID", page)
        self.assertEqual(page.count('class="set-row'), 7)                  # 2 + 2 + 2 + 1 rows, and nothing else
        self.assertLess(page.index("<h2>Privacy</h2>"), page.index('class="act-row danger"'))   # Log out comes under Privacy, in its own panel
        self.assertRegex(page, r'<div class="panel logout-panel">\s*<a class="act-row danger"')
        self.assertNotIn("<b>Emergency access</b>", page)                 # not in the design
        self.assertNotIn("tog on locked", page)

    def test_the_doctor_settings_have_their_own_rows(self):
        page = html(self.doc.get("/settings/"))
        for row in ("Patient answered", "Access ending", "Show my clinic to patients", "Download my MedScan ID", "Change password",
                    "Text size", "Language"):
            self.assertIn(f"<b>{row}</b>", page, row)
        for gone in ("Access requests", "Hidden care history", "Let doctors find me by ID"):
            self.assertNotIn(gone, page)

    def test_the_main_element_of_settings_has_the_settings_page_class_and_no_other_page_does(self):
        self.assertIn('<main class="content settings-page">', html(self.pat.get("/settings/")))
        self.assertIn('<main class="content settings-page">', html(self.doc.get("/settings/")))
        self.assertIn('<main class="content">', html(self.pat.get("/dashboard/")))

    def test_both_roles_can_download_their_id_from_settings(self):
        for client, prefix in ((self.pat, "PT-"), (self.doc, "DR-")):
            self.assertIn('href="/id/print/?auto=1"', html(client.get("/settings/")))
            printed = html(client.get("/id/print/?auto=1"))
            self.assertIn(prefix, printed)
            self.assertNotIn("pat123", printed + "")
            self.assertNotIn("doc123", printed)

    def test_the_switches_are_not_buttons_so_they_cannot_pretend_to_save(self):
        page = html(self.pat.get("/settings/")).split('<main class="content settings-page">')[1]
        self.assertNotRegex(page, r"<(button|input)[^>]*class=\"tog")
        self.assertIn("<span class=\"tog on\"><i></i></span>", page)

    def test_log_out_is_only_in_settings_and_leads_to_the_question(self):
        for client in (self.pat, self.doc):
            self.assertRegex(html(client.get("/settings/")), r'<a class="act-row danger" href="/logout/">')
            for url in ("/dashboard/", "/profile/"):
                self.assertNotIn("act-row danger", html(client.get(url)), url)
            self.assertIn("Log out of MedScan?", html(client.get("/logout/")))

    def test_every_page_header_is_the_same_shape(self):
        for client, urls in ((self.pat, ["/dashboard/", "/record/", "/access/"]), (self.doc, ["/dashboard/", "/patients/", "/search/", "/qr/"])):
            for url in urls:
                self.assertIn('<div class="head plain-h"><div>', html(client.get(url)), url)

    def test_the_header_lines_are_the_designs_words(self):
        self.assertIn("Everyone you can see, or have asked to see.", html(self.doc.get("/patients/")))
        self.assertIn("Search by MedScan ID. You'll send them a request to open their record.", html(self.doc.get("/search/")))
        self.assertIn("History can't be edited or cleared.", html(self.pat.get("/access/?tab=history")))
        self.assertNotIn("History can't be edited or cleared.", html(self.pat.get("/access/?tab=doctors")))

    def test_my_record_has_no_edit_button_in_the_header_and_the_info_tab_edit_link_opens_the_sheet(self):
        page = html(self.pat.get("/record/"))
        header = page.split('<main class="content">')[1].split('<div class="utabs">')[0]
        self.assertNotIn("Edit my information", header)
        self.assertNotIn("data-sheet", header)
        self.assertIn('<h2>Basic info</h2><a class="link" href="#" data-sheet="edit-sheet">Edit</a>', page)
        self.assertIn('<dialog id="edit-sheet"', page)
        info = page.split('data-pane="info"')[1]
        self.assertEqual(re.findall(r"<span>([A-Za-z &;]+)</span><b>", info),
                         ["Date of birth", "Age", "Sex", "Blood type", "Height", "Weight", "Mobile", "Name", "Relationship", "Mobile"])
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', info), ["Basic info", "Contact", "Emergency contact"])
        self.assertIn("Sex</span><b>Male</b>", info)

    def test_the_doctors_patient_page_has_the_designs_header_banner_tabs_and_columns(self):
        approve(self.s)
        page = html(self.doc.get("/patient/1001/"))
        main = page.split('<main class="content">')[1]
        self.assertIn('<h1>Juan Dela Cruz</h1>', main)
        self.assertRegex(main, r'<span class="pill green">Allowed</span>')
        self.assertRegex(main, r'<p><span class="num">PT-2026-01001</span> &middot; Male &middot; \d+ &middot; O\+</p>')
        self.assertLess(main.index('class="head plain-h"'), main.index('class="allergy"'))
        self.assertLess(main.index('class="allergy"'), main.index('class="utabs"'))
        tabs = re.findall(r'data-pane-tab="\w+">([A-Za-z ]+)</a>', main)
        self.assertEqual(tabs, ["Notes", "Care history", "Medical", "Info"])
        notes = main.split('data-pane="notes"')[1].split('data-pane="care"')[0]
        self.assertLess(notes.index("New consultation note"), notes.index("Consultation notes"))
        self.assertIn("Save to record", notes)
        self.assertNotIn("phrase", notes)                                  # the quick phrases are not in the design
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', notes), ["Consultation notes", "At a glance", "Seen elsewhere"])
        self.assertIn("1 entry hidden by the patient", notes)
        self.assertIn("You can't see what it is", notes)
        self.assertNotIn("Sample data", notes)

    def test_an_emergency_opening_keeps_its_banner_in_the_same_red_box_as_the_allergies(self):
        self.s.emergency_access(self.s.get_doctor(2001), 1001, "Unconscious on arrival")
        main = html(self.doc.get("/patient/1001/")).split('<main class="content">')[1]
        self.assertIn('<span class="pill red">Emergency access</span>', main)
        self.assertIn("<b>Emergency access</b><small>This was logged and Juan was notified.", main)

    def test_a_note_in_the_timeline_shows_the_date_and_the_doctor_only(self):
        approve(self.s)
        self.doc.post("/patient/1001/consult/", {"notes": "BP 130/85."})
        notes = html(self.pat.get("/record/"))
        self.assertRegex(notes, r'<div class="tl"><b>[A-Z][a-z]{2} \d+, \d{4}</b> <span class="faint small tl-meta">Dr\. Reyes</span>')

    def test_the_tabs_are_links_so_they_still_work_without_the_script(self):
        page = html(self.pat.get("/record/?tab=care"))
        self.assertIn('<a href="?tab=care" data-pane-tab="care">Care history</a>', page)


class PatientProfile(unittest.TestCase):
    """The patient's Profile page as the design draws it (reference 30)."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")

    def main(self, client):
        return html(client.get("/profile/")).split('<main class="content">')[1].split("</main>")[0]

    def test_the_header_is_the_name_and_the_id_with_the_month_the_account_began(self):
        main = self.main(self.pat)
        self.assertIn("<h1>Juan Dela Cruz</h1>", main)
        self.assertRegex(main, r'<p><span class="num">PT-2026-01001</span> &middot; Patient since [A-Z][a-z]{2} \d+, \d{4}</p>')

    def test_the_panels_and_their_rows_follow_the_design_in_order(self):
        main = self.main(self.pat)
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', main),
                         ["Personal details", "Emergency contact", "Health at a glance", "Recent care"])
        self.assertEqual(re.findall(r"<span>([A-Za-z ]+)</span><b>", main),
                         ["Date of birth", "Age", "Sex", "Blood type", "Mobile", "Name", "Relationship", "Mobile",
                          "Allergies", "Conditions", "Medication", "Last vaccine", "Given on"])
        self.assertEqual(re.findall(r'class="link"[^>]*>([A-Za-z ]+)</a>', main), ["Edit", "Edit", "My Record", "Care history"])
        self.assertNotIn("Security", main)
        self.assertNotIn('class="btn" data-sheet="contact-sheet"', main)   # the old button under the details is gone

    def test_the_real_rows_come_from_the_account(self):
        main = self.main(self.pat)
        self.assertRegex(main, r"Date of birth</span><b>[A-Z][a-z]{2} \d+, \d{4}</b>")
        self.assertRegex(main, r"Age</span><b>\d+</b>")                                   # worked out from the date of birth
        self.assertIn("Blood type</span><b>O+</b>", main)
        self.assertIn("Mobile</span><b>0917 123 4567</b>", main)
        self.assertIn('<span class="atag">Penicillin</span>', main)

    def test_personal_details_edit_opens_the_mobile_sheet_and_emergency_contact_edit_does_nothing(self):
        page = html(self.pat.get("/profile/"))
        self.assertIn('<h2>Personal details</h2><a class="link" href="#" data-sheet="contact-sheet">Edit</a>', page)
        self.assertIn('<h2>Emergency contact</h2><a class="link" href="#">Edit</a>', page)
        self.assertIn('<dialog id="contact-sheet"', page)

    def test_the_demo_patient_shows_the_sample_values(self):
        main = self.main(self.pat)
        for sample in ("Maria Dela Cruz", "Mother", "0918 765 4321", "Hypertension", "Last vaccine</span><b>Flu shot</b>", "Given on</span><b>Sep 14, 2026</b>"):
            self.assertIn(sample, main)
        self.assertNotIn("Not recorded", main)

    def test_every_other_account_says_not_recorded_instead_of_borrowing_the_samples(self):
        client = Client()
        client.post("/register/", {"role": "Patient", "name": "Zed", "password": PASSWORD, "date_of_birth": BORN,
                                   "contact_number": "0917 000 3333"})
        main = self.main(client)
        self.assertEqual(main.count("Not recorded"), 7)                   # 3 emergency contact rows, conditions, last vaccine, given on, recent care
        for sample in ("Maria Dela Cruz", "Hypertension", "Flu shot", "0918 765 4321"):
            self.assertNotIn(sample, main)
        record = html(client.get("/record/")).split('data-pane="info"')[1]
        self.assertEqual(record.count("Not recorded"), 5)                 # height, weight, and the three emergency contact rows

    def test_recent_care_repeats_the_sample_entries_of_the_care_history_tab(self):
        main = self.main(self.pat)
        recent = main.split("<h2>Recent care</h2>")[1]
        self.assertIn("<b>Consultation: Dr. Maria Reyes</b>", recent)
        self.assertIn("Oct 15, 2026 &middot; Mabini Skin Center", recent)
        self.assertIn('href="/record/?tab=care"', recent)

    def test_the_doctors_profile_keeps_its_own_page_until_the_doctor_pages_are_done(self):
        page = html(login(2001, "doc123").get("/profile/"))
        self.assertIn("Edit contact info", page)
        self.assertIn("Specialty", page)


class MyRecordAsTheDesignDrawsIt(unittest.TestCase):
    """My Record, references 15 (notes), 16 (medical) and 17 (info)."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def pane(self, name):
        page = html(self.pat.get("/record/"))
        return page.split(f'data-pane="{name}"')[1].split('<div class="pane"')[0]

    def test_notes_has_the_consultation_notes_then_written_by_then_prescribed(self):
        approve(self.s)
        self.doc.post("/patient/1001/consult/", {"notes": "BP 130/85."})
        notes = self.pane("notes")
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', notes), ["Consultation notes", "Written by", "Prescribed in these notes"])
        self.assertRegex(notes, r'<h2>Consultation notes</h2><span class="pill grey">1</span>')
        self.assertIn("<b>Dr. Reyes</b>", notes)
        self.assertIn("General Medicine &middot; 1 note</div>", notes)
        self.assertIn("<span>Amlodipine</span>", notes)

    def test_written_by_counts_notes_per_doctor(self):
        approve(self.s)
        for text in ("one", "two"):
            self.doc.post("/patient/1001/consult/", {"notes": text})
        self.assertIn("General Medicine &middot; 2 notes</div>", self.pane("notes"))

    def test_medical_has_allergies_medications_conditions_surgeries_and_vaccinations_in_order(self):
        self.s.update_patient_info(1001, "Penicillin, Peanuts", "Appendectomy", "Amlodipine 5 mg daily", "O+", "09171234567")
        medical = self.pane("medical")
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', medical),
                         ["Allergies", "Medications", "Conditions", "Past surgeries", "Vaccinations"])
        self.assertIn('<span>Penicillin</span><b><span class="atag">Severe</span>Hives, ER visit Jan 12, 2025</b>', medical)
        self.assertIn('<span class="atag mod">Moderate</span>Swelling', medical)       # moderate is the amber pill
        self.assertIn("<span>Appendectomy</span><b>Aug 9, 2021</b>", medical)
        self.assertIn("<span>Hospital</span><b>Northview Medical Center</b>", medical)
        self.assertIn("<span>Hypertension</span><b>Managed</b>", medical)
        self.assertIn("<span>Diagnosed</span><b>Jun 3, 2024</b>", medical)
        self.assertIn("<span>Tetanus (Td)</span><b>May 20, 2021</b>", medical)

    def test_a_medication_is_split_into_the_drug_and_its_dose(self):
        self.s.update_patient_info(1001, "Penicillin", "Appendectomy", "Amlodipine 5 mg daily, Aspirin", "O+", "09171234567")
        medical = self.pane("medical")
        self.assertIn("<span>Amlodipine</span><b>5 mg daily</b>", medical)
        self.assertIn("<span>Aspirin</span><b>Not recorded</b>", medical)

    def test_the_tab_panes_use_the_designs_columns(self):
        page = html(self.pat.get("/record/"))
        self.assertEqual(page.count('<div class="grid half">'), 3)         # medical (two rows of two panels) and info (one row)
        self.assertIn('<div class="chips">', page)


class AccessAsTheDesignDrawsIt(unittest.TestCase):
    """Access, references 12 (requests), 13 (doctors) and 14 (history)."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")

    def main(self, url):
        return html(self.pat.get(url)).split('<main class="content">')[1].split("</main>")[0]

    def test_requests_has_the_waiting_card_and_the_static_panel_in_order(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        main = self.main("/access/?tab=requests")
        self.assertLess(main.index("Waiting for your answer"), main.index("If you allow, the doctor can see"))
        panel = main.split("If you allow, the doctor can see")[1]
        self.assertEqual(re.findall(r'<div class="kv"><span>([A-Za-z ]+)</span>', panel), ["Basic info", "Medical", "Care history", "Notes"])
        self.assertIn('<div class="stack24">', main)
        self.assertRegex(main, r'<h2>Waiting for your answer</h2><span class="when">Today, \d\d:\d\d</span>')
        self.assertIn("Dr. Reyes wants to see your record", main)
        self.assertNotIn("Answered requests move to Doctors", main)        # no loose helper text under the panels

    def test_the_request_buttons_are_equal_and_also_repeat_for_a_phone(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        main = self.main("/access/?tab=requests")
        self.assertEqual(main.count('class="btn equal">Decline</button>'), 2)
        self.assertIn('<div class="m-only flex btn-row">', main)

    def test_doctors_lists_who_can_see_the_record_with_a_count_and_the_static_emergency_panel(self):
        approve(self.s)
        main = self.main("/access/?tab=doctors")
        self.assertRegex(main, r'<h2>Doctors who can see your record</h2><span class="pill grey">1</span>')
        self.assertIn("General Medicine &middot; allowed ", main)
        self.assertIn('<button type="submit" class="btn equal">Remove</button>', main)
        self.assertEqual(re.findall(r"<div class=\"kv\"><span>([A-Za-z' ]+)</span>", main), ["Who", "When", "Lasts", "You're told"])
        emergency = main.split("<h2>Emergency access</h2>")[1].replace("&#x27;", "'")
        for value in ("Any MedScan doctor", "If you can't answer", "1 hour", "Every time"):
            self.assertIn(f"<b>{value}</b>", emergency)

    def test_remove_still_asks_first_and_works(self):
        request = approve(self.s)
        main = self.main("/access/?tab=doctors")
        self.assertIn('data-confirm-title="Remove access?"', main)
        self.pat.post(f"/revoke/{request.request_id}/", {"next": "access"})
        self.assertEqual(self.s.access_status(2001, 1001), "revoked")

    def test_history_is_one_panel_of_rows_with_the_designs_pills_and_no_footnote(self):
        approve(self.s)
        self.s.open_record(self.s.get_doctor(2001), 1001)
        main = self.main("/access/?tab=history")
        self.assertRegex(main, r'<div class="panel">\s*<div class="list">')
        self.assertIn('<span class="pill green">Allowed</span>', main)
        self.assertIn("History can't be edited or cleared.", main)
        self.assertNotIn("This history is permanent", main)
        self.assertEqual(re.findall(r'<a href="\?tab=history[^"]*" class="[^"]*">([A-Za-z ]+) <em>', main), ["All", "QR scan", "Allowed", "Emergency"])

    def test_a_declined_request_is_in_the_history_with_a_grey_declined_pill(self):
        request = self.s.request_access(self.s.get_doctor(2001), 1001)
        self.s.respond_to_request(request.request_id, 1001, False)
        main = self.main("/access/?tab=history")
        self.assertIn("You declined Dr. Reyes", main)
        self.assertIn('<span class="pill declined">Declined</span>', main)
        items = self.s.activity_for_patient(1001)
        self.assertEqual([i["kind"] for i in items], ["declined"])
        self.assertEqual(self.s.activity_counts(items)["all"], 1)
        self.assertIn("All <em>1</em>", main)

    def test_the_doctor_sees_nothing_new_in_a_patients_history_because_a_decline_is_the_patients_own_entry(self):
        request = self.s.request_access(self.s.get_doctor(2001), 1001)
        self.s.respond_to_request(request.request_id, 1001, False)
        self.assertNotIn("You declined", html(self.doc.get("/patient/1001/")))


class AuthAndIdAsTheDesignDrawsIt(unittest.TestCase):
    """Login, sign-up, save-your-ID and the printable ID, references 01, 02, 05 and 06."""

    def test_the_teal_panel_has_the_logo_a_headline_and_one_line_and_nothing_else(self):
        for url in ("/", "/register/"):
            art = html(Client().get(url)).split('class="auth-art"')[1].split('class="auth-form"')[0]
            self.assertIn("Patient records, shared only with the doctors you trust.", art)
            self.assertIn("Show your QR code to a doctor in person, or allow their request. Every view is logged.", art)
            self.assertNotIn("feats", art)
            self.assertNotIn("SDG", art)

    def test_login_has_the_designs_words_a_show_word_and_the_demo_ids(self):
        page = html(Client().get("/"))
        self.assertIn("Log in with your MedScan ID or mobile number. Patients and doctors use the same form.", page)
        self.assertIn("MedScan ID or mobile number</label>", page)
        self.assertIn('<span class="eye-on">Show</span><span class="eye-off">Hide</span>', page)
        self.assertIn("Patient PT-2026-01001 / pat123<br>Doctor DR-2026-02001 / doc123", page)
        self.assertNotIn("Remember me", page)

    def test_sign_up_has_the_designs_words_and_says_mobile_number(self):
        page = html(Client().get("/register/")).replace("&#x27;", "'")
        self.assertIn("You'll get your MedScan ID when you finish.", page)
        self.assertIn("Mobile number</label>", page)
        self.assertNotIn("Contact number", page)
        self.assertNotIn("data-counter", page)
        self.assertIn("Already have an ID?", page)
        doctor = html(Client().get("/register/?role=doctor"))
        self.assertIn("Mobile number <span", doctor)

    def test_save_your_id_says_where_it_can_be_downloaded_again(self):
        client = Client()
        client.post("/register/", {"role": "Patient", "name": "Zed", "password": PASSWORD, "date_of_birth": BORN,
                                   "contact_number": "0917 000 6666"})
        page = html(client.get("/id/ready/"))
        self.assertIn("You can download it again any time from Settings.", page)
        self.assertRegex(page, r'class="idbig num">PT-\d{4}-\d{5}</div>')


class DoctorPagesAsTheDesignDrawsIt(unittest.TestCase):
    """The doctor's pages, references 20 to 28."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def main(self, url, client=None):
        return html((client or self.doc).get(url)).split('<main class="content">')[1].split("</main>")[0]

    # ---- Home (20)
    def test_home_has_today_and_recent_notes(self):
        main = self.main("/dashboard/")
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', main), ["Today", "Recent notes"])
        self.assertIn('<a class="link" href="/patients/">All patients</a>', main)

    def test_recent_notes_are_the_notes_this_doctor_wrote(self):
        approve(self.s)
        self.doc.post("/patient/1001/consult/", {"notes": "Follow-up: BP 130/85, headache resolved."})
        main = self.main("/dashboard/")
        notes = main.split("<h2>Recent notes</h2>")[1]
        self.assertIn("<b>Juan Dela Cruz</b>", notes)
        self.assertRegex(notes, r"[A-Z][a-z]{2} \d+, \d{4} &middot; Follow-up: BP 130/85")
        rows = self.s.recent_notes_for_doctor(2001)
        self.assertEqual([(p.user_id, n.notes) for p, n in rows], [(1001, "Follow-up: BP 130/85, headache resolved.")])

    def test_today_lists_waiting_then_allowed_then_opened(self):
        approve(self.s)
        other = new_patient(self.s, "Pedro Bautista", PASSWORD, "Male", BORN)
        self.doc.post(f"/request/{other.user_id}/")
        today = self.main("/dashboard/").split("<h2>Today</h2>")[1].split("<h2>Recent notes</h2>")[0]
        self.assertLess(today.index("Pedro Bautista"), today.index("Juan Dela Cruz"))
        self.assertIn("Waiting for him to allow your request", today)
        self.assertIn("Allowed your request", today)
        self.doc.get("/patient/1001/")
        today = self.main("/dashboard/").split("<h2>Today</h2>")[1]
        self.assertIn("Opened today", today)

    # ---- Patients (21) and Search (25)
    def test_patients_are_one_panel_with_the_designs_wording(self):
        approve(self.s)
        main = self.main("/patients/")
        self.assertRegex(main, r'<div class="panel">\s*<div class="list">')
        self.assertIn("allowed today", main)
        request = self.s.request_access(self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology"), 1001)
        self.s.respond_to_request(request.request_id, 1001, False)
        santos = login(request.doctor_id, PASSWORD)
        self.assertIn("declined today", self.main("/patients/", santos))
        self.assertIn('<span class="pill declined">Declined</span>', self.main("/patients/", santos))

    def test_search_results_are_one_panel_and_a_stranger_is_locked(self):
        main = self.main("/search/?q=1001")
        self.assertRegex(main, r'<div class="panel">\s*<div class="list">')
        self.assertIn('<span class="pill grey">Locked</span>', main)

    # ---- the locked record (22) and the emergency pop-up (26)
    def test_the_locked_record_is_one_panel_with_text_on_the_left_and_the_actions_on_the_right(self):
        main = self.main("/patient/1001/")
        self.assertIn('<div class="panel lockrow">', main)
        self.assertLess(main.index("lk-text"), main.index("lk-acts"))
        self.assertLess(main.index("lk-acts"), main.index("lk-emer"))
        self.assertIn("You need Juan's OK to open this record", main.replace("&#x27;", "'"))
        self.assertIn("If Juan is with you, scan his QR code and it opens right away. If not, send a request he can answer on his phone.", main.replace("&#x27;", "'"))
        self.assertIn("Only if the patient can't answer.", main.replace("&#x27;", "'"))
        self.assertIn("Juan is told every time.", main)

    def test_the_words_follow_the_sex_on_file(self):
        woman = new_patient(self.s, "Ana Ramos", PASSWORD, "Female", BORN)
        main = self.main(f"/patient/{woman.user_id}/").replace("&#x27;", "'")
        self.assertIn("scan her QR code", main)
        self.assertIn("a request she can answer on her phone", main)

    def test_the_emergency_pop_up_has_the_designs_words_and_still_posts(self):
        page = html(self.doc.get("/patient/1001/"))
        sheet = re.search(r'<dialog id="emergency-sheet".*?</dialog>', page, re.S).group(0).replace("&#x27;", "'")
        self.assertIn('class="sheet emer"', sheet)
        self.assertIn("This skips Juan's OK. Your name, the time and your reason are saved, and Juan is told. Access ends after 1 hour.", sheet)
        self.assertIn("Reason (required)", sheet)
        self.assertIn("This is a medical emergency", sheet)
        self.assertEqual(re.findall(r'class="btn (?:equal|solid-red) lg"[^>]*>([A-Za-z ]+)</button>', sheet), ["Cancel", "Open record"])
        r = self.doc.post("/patient/1001/emergency/", {"reason": "Collapsed", "confirm": "on"})
        self.assertEqual((r.status_code, r["Location"]), (302, "/patient/1001/"))
        self.assertEqual(count("tb_emergency_logs"), 1)

    # ---- Scan (24)
    def test_scan_has_the_camera_and_recent_scans(self):
        main = self.main("/qr/")
        self.assertIn('<div class="panel camp">', main)
        self.assertIn("Recent scans", main)
        self.assertIn("You have not scanned anyone yet.", main)
        self.assertIn('id="qr-retry" hidden', main)                            # kept: the way to try the camera again
        self.assertNotIn("Ask the patient to tap", main)

    def test_recent_scans_are_this_doctors_latest_scans_one_line_per_patient(self):
        code = self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text
        self.s.scan_qr(self.s.get_doctor(2001), code)
        main = self.main("/qr/")
        recent = main.split("<h2>Recent scans</h2>")[1]
        self.assertIn("<b>Juan Dela Cruz</b>", recent)
        self.assertRegex(recent, r"Today, \d\d:\d\d")
        self.assertEqual([p.user_id for p, when in self.s.recent_scans_for_doctor(2001)], [1001])

    # ---- Profile (27)
    def test_the_doctors_profile_has_work_details_and_this_month(self):
        main = self.main("/profile/")
        self.assertIn("<h1>Dr. Reyes</h1>", main)
        self.assertRegex(main, r'<p><span class="num">DR-\d{4}-\d{5}</span> &middot; General Medicine</p>')
        self.assertEqual(re.findall(r'<div class="sec-h"><h2>([A-Za-z ]+)</h2>', main), ["Work details", "This month"])
        self.assertEqual(re.findall(r"<span>([A-Za-z .]+)</span><b>", main),
                         ["Specialty", "Clinic", "License no.", "Mobile", "Patients seen", "Notes written", "QR scans", "Emergency access"])
        self.assertIn('<a class="link" href="#" data-sheet="contact-sheet">Edit</a>', main)
        self.assertIn("PRC 0123456", main)                                       # the sample, for demo doctor 2001 only

    def test_another_doctor_reads_not_recorded_for_the_licence(self):
        client = Client()
        client.post("/register/", {"role": "Doctor", "name": "Cruz", "password": PASSWORD, "specialty": "ENT"})
        main = self.main("/profile/", client)
        self.assertIn("License no.</span><b>Not recorded</b>", main)
        self.assertNotIn("PRC 0123456", main)

    def test_this_month_counts_what_the_doctor_did(self):
        approve(self.s)
        self.s.scan_qr(self.s.get_doctor(2001), self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text)
        self.doc.get("/patient/1001/")
        self.doc.post("/patient/1001/consult/", {"notes": "one"})
        self.doc.post("/patient/1001/consult/", {"notes": "two"})
        other = new_patient(self.s, "Em Patient", PASSWORD, "Female", BORN)
        self.doc.post(f"/patient/{other.user_id}/emergency/", {"reason": "Collapsed", "confirm": "on"})
        self.doc.get(f"/patient/{other.user_id}/")                                # opening it during the emergency counts as seeing the patient
        counts = self.s.month_counts_for_doctor(2001)
        self.assertEqual(counts, {"patients": 2, "scans": 1, "emergencies": 1, "notes": 2})
        main = self.main("/profile/")
        self.assertIn("Patients seen</span><b>2</b>", main)
        self.assertIn("Notes written</span><b>2</b>", main)
        self.assertIn("QR scans</span><b>1</b>", main)
        self.assertIn("Emergency access</span><b>1</b>", main)

    def test_a_new_doctor_starts_at_zero(self):
        newcomer = self.s.register_doctor("Cruz", PASSWORD, "ENT")
        self.assertEqual(self.s.month_counts_for_doctor(newcomer.user_id), {"patients": 0, "scans": 0, "emergencies": 0, "notes": 0})


class ExpiredQrSheet(unittest.TestCase):
    """The pop-up shows an "expired" state when the five minutes run out, instead of quietly renewing."""

    def setUp(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "gui"
        self.script = (root / "static" / "js" / "G_Qr.js").read_text(encoding="utf-8")
        self.css = (root / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")

    def test_the_script_has_the_expired_words_and_a_new_code_button(self):
        for words in ("This code has expired", "Codes last 5 minutes so nobody can reuse an old one.", "Make a new code", "data-qr-new"):
            self.assertIn(words, self.script)
        self.assertNotIn("if (left === 0) { ask(codeUrl, 'GET'); }", self.script)       # it no longer renews by itself

    def test_the_expired_code_is_blurred_with_the_button_on_top_and_a_amber_timer(self):
        self.assertIn(".sheet.expired .qrbox svg{filter:blur(5px);opacity:.25}", self.css)
        self.assertIn(".sheet.expired .timer{color:var(--amber);background:var(--amber-tint)}", self.css)
        self.assertIn(".sheet.expired #qr-new{display:none}", self.css)                  # the button on the code replaces the one below it

    def test_the_sheet_has_the_title_and_note_the_script_swaps(self):
        page = html(login(1001, "pat123").get("/dashboard/"))
        self.assertIn('id="qr-title">My QR code</h2>', page)
        self.assertIn('id="qr-note"', page)


class OneLinePerPanelAndFullDates(unittest.TestCase):
    """A second heading is its own panel, and every date shows the day, the month and the year."""

    def setUp(self):
        self.s = fresh_system(self)
        self.pat = login(1001, "pat123")
        self.doc = login(2001, "doc123")
        approve(self.s)

    def panels(self, page):
        chunks = page.split('<div class="panel')[1:]
        return [chunk.split('<div class="panel')[0] for chunk in chunks]

    def test_no_panel_has_more_than_one_heading(self):
        pages = [self.pat.get(url) for url in ("/dashboard/", "/record/", "/access/?tab=requests", "/access/?tab=doctors", "/profile/", "/settings/")]
        pages += [self.doc.get(url) for url in ("/dashboard/", "/patient/1001/", "/qr/", "/profile/")]
        for response in pages:
            for panel in self.panels(html(response)):
                self.assertLessEqual(panel.count('class="sec-h"'), 1, panel[:120])

    def test_past_surgeries_prescribed_and_seen_elsewhere_are_their_own_panels(self):
        record = html(self.pat.get("/record/"))
        medical = record.split('data-pane="medical"')[1].split('data-pane="info"')[0]
        self.assertEqual(len(re.findall(r'<div class="panel">\s*<div class="sec-h"><h2>(?:Conditions|Past surgeries)</h2>', medical)), 2)
        notes = record.split('data-pane="notes"')[1].split('data-pane="care"')[0]
        self.assertRegex(notes, r'<div class="panel">\s*<section class="sec">\s*<div class="sec-h"><h2>Prescribed in these notes</h2>')
        glance = html(self.doc.get("/patient/1001/")).split("At a glance")[1]
        self.assertRegex(glance, r'</div>\s*<div class="panel">\s*<section class="sec">\s*<div class="sec-h"><h2>Seen elsewhere</h2>')

    def test_the_filters_print_the_year_for_an_older_date(self):
        from datetime import datetime
        from gui.G_Filters import day, when
        older = datetime(2025, 3, 7, 14, 5)
        self.assertEqual(day(older), "Mar 7, 2025")
        self.assertEqual(when(older), "Mar 7, 2025, 14:05")
        self.assertEqual(when(older, "date"), "Mar 7, 2025")
        self.assertEqual(when(datetime.now()).split(",")[0], "Today")           # today and yesterday keep their words

    def test_the_real_dates_on_the_pages_have_a_year(self):
        self.doc.get("/patient/1001/")
        self.doc.post("/patient/1001/consult/", {"notes": "BP ok."})
        home = html(self.pat.get("/dashboard/"))
        self.assertRegex(home, r"Last visit<b>[A-Z][a-z]{2} \d+, \d{4}</b>")
        self.assertRegex(html(self.pat.get("/access/?tab=doctors")), r"allowed (?:by QR scan, )?[A-Z][a-z]{2} \d+, \d{4}")
        self.assertRegex(html(self.doc.get("/dashboard/")), r"[A-Z][a-z]{2} \d+, \d{4} &middot; BP ok\.")

    def test_the_sample_dates_match_the_design(self):
        record = html(self.pat.get("/record/"))
        for date in ("Nov 8, 2024", "Aug 9, 2021", "last Mar 7, 2025", "last Oct 16, 2026", "last Oct 15, 2026", "Jan 12, 2025", "Jun 3, 2024",
                     "Sep 14, 2026", "May 20, 2021"):
            self.assertIn(date, record)
        profile = html(self.pat.get("/profile/"))
        self.assertIn("Given on</span><b>Sep 14, 2026</b>", profile)
        self.assertRegex(profile, r"Patient since [A-Z][a-z]{2} \d+, \d{4}")
        self.assertIn("Surgery date</span><b>Aug 9, 2021</b>", html(self.doc.get("/patient/1001/")))
        self.assertNotIn("Surgery year", html(self.doc.get("/patient/1001/")))

    def test_the_label_is_bold_with_a_colon_and_the_value_is_plain(self):
        css = (Path(__file__).resolve().parent.parent / "gui" / "static" / "css" / "G_Style.css").read_text(encoding="utf-8")
        for rule in (".kvs .kv>span{font-weight:600!important;color:#12333A!important}", '.kvs .kv>span::after{content:":"}',
                     ".kvs .kv>b{font-weight:400!important;color:#12333A}"):
            self.assertIn(rule, css)


if __name__ == "__main__":
    unittest.main()
