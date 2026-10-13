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


class PatientGroups(Doctors):
    def test_each_patient_is_in_one_group_by_the_newest_request(self):
        yes, wait, no, back = (self.patient(n) for n in ["Yes", "Wait", "No", "Back"])
        self.ask(yes, True)
        self.ask(wait)
        self.ask(no, False)
        revoked = self.ask(back, True)
        self.s.revoke_access(revoked.request_id, back.user_id)
        groups = self.s.patient_groups_for_doctor(2001)
        names = lambda key: sorted(p.name for _, p in groups[key])
        self.assertEqual((names("mine"), names("waiting"), names("ended")), (["Yes"], ["Wait"], ["Back", "No"]))

    def test_asking_again_moves_a_patient_to_waiting_and_not_into_two_groups(self):
        no = self.patient("No")
        self.ask(no, False)
        self.ask(no)
        groups = self.s.patient_groups_for_doctor(2001)
        self.assertEqual(([p.name for _, p in groups["waiting"]], groups["ended"]), (["No"], []))

    def test_the_patients_come_with_their_records_for_the_list(self):
        yes = self.patient("Yes", allergies="Latex")
        self.ask(yes, True)
        (_, patient), = self.s.patient_groups_for_doctor(2001)["mine"]
        self.assertEqual(patient.record.allergies, ["Latex"])

    def test_another_doctors_patients_are_not_mine(self):
        other = self.s.register_doctor("Cruz", PASSWORD, "ENT")
        self.ask(self.patient("Theirs"), True, doctor=other)
        self.assertEqual(self.s.patient_groups_for_doctor(2001), {"mine": [], "waiting": [], "ended": []})


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
        execute("UPDATE record_views SET created_at = created_at - INTERVAL 20 MINUTE")
        self.s.open_record(self.reyes, people[0].user_id)   # opened again: now the newest
        recent = self.s.recent_patients_for_doctor(2001, limit=5)
        self.assertEqual([p.name for p in recent], ["P0", "P6", "P5", "P4", "P3"])

    def test_recent_leaves_out_patients_who_took_access_back(self):
        ana, bea = self.patient("Ana"), self.patient("Bea")
        ask_ana = self.ask(ana, True)
        self.ask(bea, True)
        self.s.open_record(self.reyes, ana.user_id)
        self.s.open_record(self.reyes, bea.user_id)
        self.s.revoke_access(ask_ana.request_id, ana.user_id)
        self.assertEqual([p.name for p in self.s.recent_patients_for_doctor(2001)], ["Bea"])

    def test_an_emergency_opened_record_is_recent_until_the_hour_is_up(self):
        stranger = self.patient("Stranger")
        self.s.emergency_access(self.reyes, stranger.user_id, "Collapsed")
        self.s.open_record(self.reyes, stranger.user_id)
        self.assertEqual([p.name for p in self.s.recent_patients_for_doctor(2001)], ["Stranger"])
        execute("UPDATE emergency_logs SET created_at = created_at - INTERVAL 61 MINUTE")
        self.assertEqual(self.s.recent_patients_for_doctor(2001), [])


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
        for text in ["%", "'; DROP TABLE patients; --", "<script>", "\\", "x" * 500]:
            self.assertEqual(self.names(text), [])


class WhatHappenedToMyRecord(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def test_views_and_emergency_uses_are_one_feed_newest_first(self):
        approve(self.s)
        self.s.open_record(self.reyes, 1001)
        execute("UPDATE record_views SET created_at = created_at - INTERVAL 5 MINUTE")
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
        execute("UPDATE patients SET name = '<b>Juan</b>' WHERE user_id = 1001")
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
        self.assertRegex(page, r'<span class="faint small" title="[A-Z][a-z]{2} \d\d, \d{4} \d\d:\d\d">just now</span>')


class LoginRemembersTheId(unittest.TestCase):
    def test_the_box_and_the_hooks(self):
        page = html(Client().get("/"))
        field = re.search(r'<input[^>]*name="user_id"[^>]*>', page).group(0)
        self.assertIn('data-remember="medscan_login_id"', field)
        self.assertIn('data-remember-box="remember"', field)
        self.assertRegex(page, r'<input type="checkbox" id="remember"> Remember my ID on this computer')

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
        for script in ["G_Suggest.js", "G_Emergency.js"]:
            self.assertIn(script, doctor)
            self.assertNotIn(script, patient)
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
    """The sign-up and home screens: role choice first, short forms, the profile nudge, the doctor's week chart, the search dim."""

    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    def test_signing_up_starts_with_a_choice_of_two_equal_tiles(self):
        page = html(Client().get("/register/"))
        self.assertEqual(page.count('class="role-tile"'), 2)
        self.assertIn('href="?role=patient"', page)
        self.assertIn('href="?role=doctor"', page)
        self.assertNotIn("<form", page)            # no form until a role is chosen

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
        for field in ("contact_number", "date_of_birth", "allergies"):
            self.assertNotIn(f'name="{field}"', doctor)

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

    def test_an_unknown_role_in_the_address_shows_the_choice_again(self):
        self.assertEqual(html(Client().get("/register/?role=admin")).count('class="role-tile"'), 2)

    def test_the_profile_card_counts_what_is_still_missing(self):
        patient = self.s.get_patient(1001)
        progress = self.s.profile_progress(patient)
        self.assertEqual(progress["todo"], ["Medications"])         # the seed has blood type and an allergy
        self.assertEqual(progress["percent"], 80)
        bare = new_patient(self.s, "Bare", PASSWORD, "F", BORN)
        progress = self.s.profile_progress(self.s.get_patient(bare.user_id))
        self.assertEqual(progress["todo"], ["Blood type", "Allergies", "Medications"])
        self.assertEqual(progress["percent"], 40)

    def test_the_nudge_card_shows_while_something_is_missing_and_disappears_when_complete(self):
        page = html(self.pat.get("/dashboard/"))
        self.assertIn("Finish your health profile", page)
        self.assertIn('data-hide-key="medscan_hide_profile_nudge"', page)
        self.s.update_patient_info(1001, "Penicillin", "Appendectomy", "Amlodipine", "O+", "09171234567")
        self.assertNotIn("Finish your health profile", html(self.pat.get("/dashboard/")))

    def test_an_empty_allergy_list_says_none_recorded_not_no_known_allergies(self):
        bare = new_patient(self.s, "Bare", PASSWORD, "F", BORN)
        approve(self.s, 2001, bare.user_id)
        mine = login(bare.user_id, PASSWORD)
        pages = [html(mine.get("/dashboard/")), html(mine.get("/record/")), html(self.doc.get(f"/patient/{bare.user_id}/"))]
        for page in pages:
            self.assertNotIn("No known allergies", page)
        self.assertIn("None recorded", pages[0])
        self.assertIn("None recorded", pages[2])

    def test_the_doctors_week_has_seven_bars_ending_today(self):
        week = self.s.notes_this_week(2001)
        self.assertEqual(len(week), 7)
        self.assertEqual([d["today"] for d in week], [False] * 6 + [True])
        self.assertTrue(all(d["count"] == 0 and d["height"] == 4 for d in week))

    def test_a_note_written_today_shows_in_todays_bar(self):
        approve(self.s)
        self.s.add_consultation(self.s.get_doctor(2001), 1001, "Checked.")
        week = self.s.notes_this_week(2001)
        self.assertEqual((week[-1]["count"], week[-1]["height"]), (1, 100))
        page = html(self.doc.get("/dashboard/"))
        self.assertEqual(len(re.findall(r'class="bar( today)?"', page)), 7)
        self.assertIn("1 note", page)

    def test_the_doctor_home_has_four_equal_stat_cards_and_four_equal_panels(self):
        page = html(self.doc.get("/dashboard/"))
        self.assertEqual(page.count('class="card kpi"'), 4)
        for heading in ("Ready to open", "Notes this week", "Recently opened", "Latest activity"):
            self.assertIn(f"<h2>{heading}</h2>", page)

    def test_the_patients_page_is_a_table_with_a_header_row(self):
        approve(self.s)
        page = html(self.doc.get("/patients/"))
        self.assertIn("rowgrid head", page)
        self.assertIn("<span>Allergies</span>", page)
        self.assertIn("Penicillin", page)

    def test_the_search_result_has_two_equal_buttons(self):
        page = html(self.doc.get("/patients/?q=1001"))
        self.assertIn('class="split"', page)
        self.assertIn("Send access request", page)
        self.assertIn("Emergency access", page)

    def test_the_page_has_a_dim_layer_for_the_search_box_and_the_script_uses_it(self):
        from pathlib import Path
        self.assertIn('id="search-scrim"', html(self.doc.get("/dashboard/")))
        script = (Path(__file__).resolve().parent.parent / "gui" / "static" / "js" / "G_Suggest.js").read_text(encoding="utf-8")
        self.assertIn("'focus'", script)
        self.assertIn("searching", script)

    def test_the_templates_use_no_inline_styles_except_the_bar_heights_and_progress(self):
        from pathlib import Path
        folder = Path(__file__).resolve().parent.parent / "gui" / "templates"
        for path in folder.glob("*.html"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if 'style="' in line:
                    self.assertTrue("height:{{" in line or "width:{{" in line, f"{path.name}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
