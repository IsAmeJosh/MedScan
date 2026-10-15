"""The website, page by page, for both roles: login, registration, search, requests, records, emergencies,
notifications and the rules that keep each role in its own pages."""
import re
import unittest

from django.test import Client

from tests.helpers import (BORN, PASSWORD, age_emergencies, approve, count, fresh_system, html, login, rows)
from tests.helpers import new_patient

DOCTOR_PAGES = ["/dashboard/", "/patients/", "/patients/?q=1001", "/patients/?tab=waiting", "/patients/?tab=ended",
                "/emergency/", "/logout/"]
PATIENT_PAGES = ["/dashboard/", "/record/", "/privacy/", "/privacy/?tab=activity", "/logout/"]


class PageTestCase(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")


class BeforeLogin(PageTestCase):
    def test_login_and_register_pages(self):
        anon = Client()
        r = anon.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("auth-page", html(r))
        self.assertEqual(anon.get("/register/").status_code, 200)

    def test_pages_that_need_a_login_send_you_to_the_login_page(self):
        anon = Client()
        for url in ["/dashboard/", "/patients/", "/record/", "/privacy/", "/emergency/", "/logout/", "/patient/1001/"]:
            r = anon.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(r["Location"], ("/", "/dashboard/"), url)

    def test_the_addresses_of_earlier_versions_lead_to_the_page_that_replaced_them(self):
        anon = Client()
        for old, new in [("/search/", "/patients/"), ("/search/?q=1001", "/patients/?q=1001"),
                         ("/requests/", "/patients/?tab=waiting"), ("/doctors/", "/privacy/"),
                         ("/access-log/", "/privacy/?tab=activity"), ("/profile/", "/record/")]:
            r = anon.get(old)
            self.assertEqual((r.status_code, r["Location"]), (302, new), old)
        self.assertEqual(anon.get("/welcome/").status_code, 404)

    def test_login_accepts_the_number_and_the_display_id(self):
        for user_id in ["2001", self.s.get_doctor(2001).display_id, self.s.get_doctor(2001).display_id.lower()]:
            self.assertEqual(Client().post("/", {"user_id": user_id, "password": "doc123"}).status_code, 302, user_id)
        patient_id = self.s.get_patient(1001).display_id
        self.assertEqual(Client().post("/", {"user_id": patient_id, "password": "pat123"}).status_code, 302)

    def test_wrong_details_and_missing_fields_show_a_message_and_never_crash(self):
        anon = Client()
        self.assertIn("Wrong ID number or password.", html(anon.post("/", {"user_id": "2001", "password": "nope"})))
        self.assertIn("Wrong ID number or password.", html(anon.post("/", {"user_id": "abc", "password": "x"})))
        self.assertEqual(anon.post("/", {}).status_code, 200)

    def test_a_logged_in_user_skips_login_and_register(self):
        self.assertEqual(self.pat.get("/").status_code, 302)
        self.assertEqual(self.pat.get("/register/").status_code, 302)

    def test_logout_asks_first_and_then_ends_the_session(self):
        self.assertIn("Log out of MedScan", html(self.pat.get("/logout/")))
        self.assertEqual(self.pat.get("/dashboard/").status_code, 200)
        self.assertEqual(self.pat.post("/logout/").status_code, 302)
        self.assertEqual(self.pat.get("/dashboard/").status_code, 302)


class Registration(PageTestCase):
    def form(self, **changes):
        data = {"role": "Patient", "name": "Zed", "password": PASSWORD, "date_of_birth": BORN,
                "contact_number": "0917 000 1111"}
        data.update(changes)
        return data

    def test_registering_logs_you_in_and_opens_the_dashboard_with_an_id_card(self):
        client = Client()
        r = client.post("/register/", self.form())
        self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/"))
        page = html(client.get("/dashboard/"))
        self.assertIn("Welcome to MedScan, Zed!", page)
        shown = re.search(r"PT-\d{4}-(\d{5})", page)
        self.assertTrue(shown)
        self.assertIn("data-copy=", page)                     # the Copy ID button
        self.assertIn("or your mobile number", page)         # and how else to get back in
        self.assertNotIn("Welcome to MedScan, Zed!", html(client.get("/dashboard/")))   # shown once
        self.assertEqual(client.get("/record/").status_code, 200)                       # really logged in
        new_id = int(shown.group(1))
        self.assertEqual(rows("SELECT contact_number FROM patients WHERE user_id = %s", new_id)[0]["contact_number"],
                         "09170001111")

    def test_the_new_account_can_log_in_by_number_by_full_id_and_by_mobile(self):
        client = Client()
        client.post("/register/", self.form())
        page = html(client.get("/dashboard/"))
        new_id = int(re.search(r"PT-\d{4}-(\d{5})", page).group(1))
        display = re.search(r"PT-\d{4}-\d{5}", page).group(0)
        for typed in [str(new_id), display, "0917 000 1111", "09170001111", "+63 917 000 1111", "639170001111"]:
            r = Client().post("/", {"user_id": typed, "password": PASSWORD})
            self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/"), typed)

    def test_a_doctor_registers_and_lands_on_the_dashboard_too(self):
        client = Client()
        r = client.post("/register/", {"role": "Doctor", "name": "Cruz", "password": PASSWORD,
                                       "specialty": "ENT", "clinic": "  Rizal Clinic "})
        self.assertEqual(r["Location"], "/dashboard/")
        page = html(client.get("/dashboard/"))
        self.assertIn("Welcome to MedScan, Cruz!", page)
        self.assertIn("DR-", page)
        self.assertNotIn("your mobile number", page)   # doctors log in with their ID
        self.assertEqual(rows("SELECT clinic, specialty FROM doctors ORDER BY user_id DESC LIMIT 1")[0],
                         {"clinic": "Rizal Clinic", "specialty": "ENT"})

    def test_the_old_welcome_page_is_gone(self):
        self.assertEqual(Client().get("/welcome/").status_code, 404)

    def test_a_patient_must_give_a_mobile_number(self):
        before = count("patients")
        r = Client().post("/register/", self.form(contact_number=""))
        self.assertEqual(r.status_code, 200)
        self.assertIn("Enter your mobile number.", html(r))
        self.assertEqual(count("patients"), before)

    def test_one_mobile_number_is_one_account_however_it_is_written(self):
        Client().post("/register/", self.form())
        before = count("patients")
        for typed in ["0917 000 1111", "09170001111", "+63 917 000 1111", "63-917-000-1111"]:
            r = Client().post("/register/", self.form(name="Copy", contact_number=typed))
            self.assertEqual(r.status_code, 200, typed)
            self.assertIn("already used by another account", html(r), typed)
        self.assertEqual(count("patients"), before)

    def test_the_form_keeps_what_was_typed_when_the_number_is_taken(self):
        r = Client().post("/register/", self.form(contact_number="0917 123 4567"))   # Juan's number
        self.assertIn('value="Zed"', html(r))

    def test_empty_or_broken_forms_never_crash(self):
        client = Client()
        for data in [{}, {"role": "Patient"}, {"role": "Patient", "name": "Zed"}, {"role": "Doctor", "name": "X"}]:
            self.assertEqual(client.post("/register/", data).status_code, 200, data)


class DoctorPages(PageTestCase):
    def test_every_page_renders_with_the_doctor_menu(self):
        for url in DOCTOR_PAGES:
            r = self.doc.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn("Dr. Reyes", html(r), url)

    def test_the_menu_is_home_and_patients_with_search_and_emergency_in_the_top_bar(self):
        page = html(self.doc.get("/dashboard/"))
        nav = re.search(r'<nav class="nav">(.*?)</nav>', page, re.S).group(1)
        self.assertEqual(re.findall(r"</svg>([A-Za-z ]+)(?:<span|</a>)", nav), ["Home", "Patients", "Scan QR"])
        for gone in ["Search Patient", "My Requests", "My Patients", "Emergency Access"]:
            self.assertNotIn(gone, nav)
        self.assertIn('id="top-search-input"', page)
        self.assertIn('action="/patients/"', page)
        self.assertRegex(page, r'<a class="btn danger-ghost sm" href="/emergency/" data-emergency>')

    def test_search_by_number_display_id_and_mobile_number(self):
        for query in ["1001", self.s.get_patient(1001).display_id, "0917 123 4567", "+63 917 123 4567", "09171234567"]:
            page = html(self.doc.get("/patients/", {"q": query}))
            self.assertIn("Juan Dela Cruz", page, query)
            self.assertIn("Send access request", page, query)
            self.assertIn("This record is private", page, query)

    def test_search_by_name_only_finds_your_own_patients(self):
        self.assertIn("No patient found", html(self.doc.get("/patients/?q=Juan")))   # not approved yet: not yours
        approve(self.s)
        page = html(self.doc.get("/patients/?q=juan"))
        self.assertIn("Your patients matching", page)
        self.assertIn("Open record", page)

    def test_search_for_nobody_or_nonsense_is_polite(self):
        for query in ["9999", "abc", "2001", "0917 999 9999", "%C2%B2", "x" * 300]:
            r = self.doc.get("/patients/", {"q": query})
            self.assertEqual(r.status_code, 200, query)
            self.assertIn("No patient found", html(r), query)   # a doctor's ID is not a patient

    def test_search_shows_each_state_of_a_request(self):
        self.doc.post("/request/1001/")
        page = html(self.doc.get("/patients/?q=1001"))
        self.assertIn("Request pending", page)
        self.assertNotIn("Send access request", page)
        request = rows("SELECT request_id FROM access_requests")[0]["request_id"]
        self.s.respond_to_request(request, 1001, False)
        page = html(self.doc.get("/patients/?q=1001"))
        self.assertIn("Access denied", page)
        self.assertIn("Request again", page)
        self.doc.post("/request/1001/")
        newest = rows("SELECT MAX(request_id) AS r FROM access_requests")[0]["r"]
        self.s.respond_to_request(newest, 1001, True)
        self.assertIn("Access approved", html(self.doc.get("/patients/?q=1001")))
        self.s.revoke_access(newest, 1001)
        page = html(self.doc.get("/patients/?q=1001"))
        self.assertIn("Access revoked", page)
        self.assertIn("Request again", page)

    def test_sending_a_request_comes_back_to_the_result_with_a_message(self):
        r = self.doc.post("/request/1001/")
        self.assertEqual(r["Location"], "/patients/?q=1001")
        self.assertIn("Request pending", html(self.doc.get(r["Location"])))

    def test_sending_a_second_request_shows_a_message(self):
        self.doc.post("/request/1001/")
        r = self.doc.post("/request/1001/", follow=True)
        self.assertIn("already have access or a pending request", html(r))
        self.assertEqual(count("access_requests"), 1)

    def test_the_three_tabs_follow_the_newest_request_with_each_patient(self):
        self.assertIn("No patient has approved you yet", html(self.doc.get("/patients/")))
        yes = new_patient(self.s, "Yes Patient", PASSWORD, "F", BORN)
        wait = new_patient(self.s, "Wait Patient", PASSWORD, "F", BORN)
        no = new_patient(self.s, "No Patient", PASSWORD, "F", BORN)
        doctor = self.s.get_doctor(2001)
        for patient, answer in [(yes, True), (wait, None), (no, False)]:
            request = self.s.request_access(doctor, patient.user_id)
            if answer is not None:
                self.s.respond_to_request(request.request_id, patient.user_id, answer)
        mine, waiting, ended = (html(self.doc.get(f"/patients/?tab={t}")) for t in ("mine", "waiting", "ended"))
        names = lambda page: re.findall(r'<div><b>([A-Za-z ]+ Patient)</b><span>', page)
        self.assertEqual((names(mine), names(waiting), names(ended)), (["Yes Patient"], ["Wait Patient"], ["No Patient"]))
        self.assertIn("Ask again", ended)
        self.assertRegex(mine, r"My patients <span>1</span>")
        self.assertRegex(mine, r"Waiting for an answer <span>1</span>")
        self.assertRegex(mine, r"Declined or ended <span>1</span>")
        # the one who said no is asked again, and moves to Waiting
        self.doc.post(f"/request/{no.user_id}/")
        self.assertEqual(names(html(self.doc.get("/patients/?tab=waiting"))), ["No Patient", "Wait Patient"])
        self.assertEqual(names(html(self.doc.get("/patients/?tab=ended"))), [])

    def test_an_unknown_tab_shows_my_patients(self):
        approve(self.s)
        self.assertIn("Juan Dela Cruz", html(self.doc.get("/patients/?tab=bogus")))

    def test_the_record_is_locked_until_approved_and_nothing_is_logged(self):
        r = self.doc.get("/patient/1001/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/patients/?q=1001"))
        self.assertEqual(count("record_views"), 0)
        self.doc.post("/patient/1001/consult/", {"notes": "sneaky"})
        self.assertEqual(count("consultations"), 0)

    def test_record_page_shows_everything_after_approval(self):
        approve(self.s)
        page = html(self.doc.get("/patient/1001/"))
        for text in ["Allergies", "Penicillin", "Appendectomy", "O+", "0917 123 4567"]:
            self.assertIn(text, page)

    def test_a_note_is_saved_and_the_patient_sees_it(self):
        approve(self.s)
        self.doc.post("/patient/1001/consult/", {"notes": "Fever"})
        self.doc.post("/patient/1001/consult/", {"notes": "   "})
        self.assertEqual(count("consultations"), 1)
        self.assertIn("Fever", html(self.doc.get("/patient/1001/")))
        self.assertIn("Fever", html(self.pat.get("/record/")))

    def test_reopening_the_record_is_logged_once_and_shown_to_the_patient(self):
        approve(self.s)
        for _ in range(3):
            self.doc.get("/patient/1001/")
        self.assertEqual(count("record_views"), 1)
        self.assertIn("Dr. Reyes opened your record", html(self.pat.get("/dashboard/")))
        self.assertIn("Dr. Reyes opened your record", html(self.pat.get("/privacy/?tab=activity")))

    def test_home_lists_new_approvals_until_the_record_is_opened_then_recent_patients(self):
        self.assertIn("Nobody is waiting", html(self.doc.get("/dashboard/")))
        approve(self.s)
        home = html(self.doc.get("/dashboard/"))
        self.assertIn("approved your request", home)
        self.assertNotIn("Nobody is waiting", home)
        self.assertRegex(html(self.doc.get("/patients/")), r'id="count-ready" >1<')   # and the menu says so
        self.doc.get("/patient/1001/")
        home = html(self.doc.get("/dashboard/"))
        self.assertNotIn("approved your request", home)
        self.assertIn("Recently opened", home)
        self.assertIn("Juan Dela Cruz", home)
        self.assertRegex(html(self.doc.get("/patients/")), r'id="count-ready" hidden>0<')

    def test_a_patient_who_took_access_back_leaves_the_recent_list(self):
        request = approve(self.s)
        self.doc.get("/patient/1001/")
        self.s.revoke_access(request.request_id, 1001)
        self.assertIn("Records you open show up here", html(self.doc.get("/dashboard/")))   # the list is empty again


class EmergencyPages(PageTestCase):
    def test_a_reason_is_required_and_the_patient_must_exist(self):
        r = self.doc.post("/emergency/", {"patient_id": "PT-2026-01001", "reason": ""})
        self.assertIn("reason is required", html(r))
        r = self.doc.post("/emergency/", {"patient_id": "9999", "reason": "x"})
        self.assertIn("No patient with that ID", html(r))
        self.assertEqual(count("emergency_logs"), 0)

    def test_the_page_can_be_prefilled_from_a_patient(self):
        self.assertIn("Juan Dela Cruz", html(self.doc.get("/patient/1001/emergency/")))

    def test_a_patient_can_be_named_by_id_or_by_mobile_number(self):
        for typed in ["1001", "PT-2026-01001", "0917 123 4567", "+63 917 123 4567"]:
            self.assertEqual(self.doc.post("/emergency/", {"patient_id": typed, "reason": "Collapsed"}).status_code, 302, typed)

    def test_it_opens_the_record_with_a_banner_and_tells_the_patient(self):
        r = self.doc.post("/emergency/", {"patient_id": "1001", "reason": "Collapsed"})
        self.assertEqual((r.status_code, r["Location"]), (302, "/patient/1001/"))
        page = html(self.doc.get("/patient/1001/"))
        self.assertIn("Emergency access", page)
        activity = html(self.pat.get("/privacy/?tab=activity"))
        self.assertIn("used emergency access", activity)
        self.assertIn("Reason: Collapsed", activity)
        self.assertIn("emergency: Collapsed", html(self.pat.get("/dashboard/")))
        self.assertEqual(rows("SELECT via FROM record_views")[0]["via"], "emergency")

    def test_notes_are_allowed_during_the_emergency_and_stop_after_an_hour(self):
        self.doc.post("/patient/1001/emergency/", {"reason": "Collapsed"})
        self.doc.post("/patient/1001/consult/", {"notes": "ER note"})
        self.assertEqual(count("consultations"), 1)
        age_emergencies(61)
        self.assertEqual(self.doc.get("/patient/1001/").status_code, 302)
        self.doc.post("/patient/1001/consult/", {"notes": "too late"})
        self.assertEqual(count("consultations"), 1)

    def test_doctors_get_the_pop_up_on_every_page_and_patients_do_not(self):
        for url in ["/dashboard/", "/patients/", "/patients/?q=1001"]:
            self.assertIn('id="emergency-dialog"', html(self.doc.get(url)), url)
        for url in ["/dashboard/", "/record/", "/privacy/"]:
            self.assertNotIn("emergency-dialog", html(self.pat.get(url)), url)
            self.assertNotIn("data-emergency", html(self.pat.get(url)), url)

    def test_the_pop_up_has_a_reason_box_with_a_counter_and_asks_for_the_patient_when_it_does_not_know(self):
        page = html(self.doc.get("/dashboard/"))
        dialog = re.search(r'<dialog id="emergency-dialog".*?</dialog>', page, re.S).group(0)
        self.assertIn('maxlength="500"', dialog)
        self.assertIn("data-counter", dialog)
        self.assertIn('name="patient_id"', dialog)
        self.assertIn("without the patient's approval", dialog)

    def test_a_search_result_opens_the_pop_up_for_that_patient(self):
        link = re.search(r"<a[^>]*data-patient-id=[^>]*>", html(self.doc.get("/patients/?q=1001"))).group(0)
        self.assertIn('data-emergency', link)
        self.assertIn('data-patient-id="1001"', link)
        self.assertIn('data-patient-name="Juan Dela Cruz (PT-', link)
        self.assertIn('href="/patient/1001/emergency/"', link)   # and without scripts it is a normal link


class PatientPages(PageTestCase):
    def test_every_page_renders_with_the_patient_menu(self):
        for url in PATIENT_PAGES:
            r = self.pat.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn("Juan Dela Cruz", html(r), url)

    def test_the_menu_is_home_my_health_and_privacy(self):
        nav = re.search(r'<nav class="nav">(.*?)</nav>', html(self.pat.get("/dashboard/")), re.S).group(1)
        self.assertEqual(re.findall(r"</svg>([A-Za-z ]+)(?:<span|</a>)", nav), ["Home", "My Health", "Privacy", "My QR Code"])
        for gone in ["My Doctors", "Access Log", "Profile", "My Record"]:
            self.assertNotIn(gone, nav)

    def test_the_dashboard_shows_the_age_worked_out_from_the_date_of_birth(self):
        self.assertIn(f"{self.s.get_patient(1001).age} years", html(self.pat.get("/dashboard/")))

    def test_my_health_has_everything_the_old_profile_had(self):
        page = html(self.pat.get("/record/"))
        for text in ["PT-2026-01001", "0917 123 4567", "Member since", "O+", "Penicillin", "Appendectomy", "Edit my information"]:
            self.assertIn(text, page)
        self.assertIn('data-open="edit"', page)
        self.assertIn('id="edit"', page)

    def test_editing_info_replaces_the_lists_and_saves_them(self):
        r = self.pat.post("/record/edit/", {"allergies": "Peanuts, Latex", "surgeries": "", "medications": "Metformin",
                                            "blood_type": "A+", "contact_number": "0917 555 1234"}, follow=True)
        self.assertIn("Your information was updated.", html(r))
        juan = self.s.get_patient(1001)
        self.assertEqual((juan.record.allergies, juan.record.surgeries, juan.record.medications),
                         (["Peanuts", "Latex"], [], ["Metformin"]))
        self.assertEqual((juan.record.blood_type, juan.contact_number), ("A+", "09175551234"))

    def test_a_bad_edit_shows_the_reason_and_changes_nothing(self):
        r = self.pat.post("/record/edit/", {"allergies": "Peanuts", "contact_number": "12"}, follow=True)
        self.assertIn("Enter a valid mobile number", html(r))
        self.assertEqual(self.s.get_patient(1001).record.allergies, ["Penicillin"])

    def test_home_asks_for_an_answer_first_and_the_buttons_work(self):
        self.assertNotIn("Waiting for your answer", html(self.pat.get("/dashboard/")))
        request = self.s.request_access(self.s.get_doctor(2001), 1001)
        page = html(self.pat.get("/dashboard/"))
        self.assertIn("Waiting for your answer", page)
        self.assertIn("Dr. Reyes wants to open your record", page)
        r = self.pat.post(f"/respond/{request.request_id}/approve/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/"))
        self.assertNotIn("Waiting for your answer", html(self.pat.get("/dashboard/")))
        self.assertEqual(self.s.access_status(2001, 1001), "approved")

    def test_privacy_groups_doctors_by_status_and_answers_requests(self):
        approved = approve(self.s)
        santos = self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview Medical Center")
        waiting = self.s.request_access(santos, 1001)
        page = html(self.pat.get("/privacy/"))
        self.assertIn("Doctor in <b>General Medicine</b> at <b>Bayanihan Family Clinic</b>", page)
        self.assertIn("Waiting for your answer", page)
        self.assertIn("Can open your record", page)
        r = self.pat.post(f"/respond/{waiting.request_id}/approve/", {"next": "privacy"})
        self.assertEqual((r.status_code, r["Location"]), (302, "/privacy/"))
        r = self.pat.post(f"/revoke/{approved.request_id}/", {"next": "privacy"})
        self.assertEqual(r["Location"], "/privacy/")
        self.assertIn("Past access", html(self.pat.get("/privacy/")))

    def test_privacy_tab_counts_and_an_empty_state(self):
        page = html(self.pat.get("/privacy/"))
        self.assertIn("No doctor has asked for access yet", page)
        self.assertRegex(page, r"Doctors <span>0</span>")
        approve(self.s)
        self.assertRegex(html(self.pat.get("/privacy/")), r"Doctors <span>1</span>")

    def test_the_activity_tab_mixes_record_views_and_emergency_uses_newest_first(self):
        approve(self.s)
        doctor = self.s.get_doctor(2001)
        self.s.open_record(doctor, 1001)
        self.s.emergency_access(doctor, 1001, "Collapsed in the lobby")
        page = html(self.pat.get("/privacy/?tab=activity"))
        self.assertRegex(page, r"Who opened my record <span>2</span>")
        self.assertLess(page.index("used emergency access"), page.index("opened your record"))   # newest first
        self.assertIn("Reason: Collapsed in the lobby", page)

    def test_the_doctor_is_notified_with_the_patients_name(self):
        self.doc.post("/request/1001/")
        self.pat.post(f"/respond/{rows('SELECT request_id FROM access_requests')[0]['request_id']}/approve/")
        self.assertTrue(any("Juan Dela Cruz approved" in n.message for n in self.s.inbox(2001)))

    def test_the_scanner_lives_on_its_own_page_not_on_patients(self):
        self.assertNotIn("scan-button", html(self.doc.get("/patients/")))


class RolesStayApart(PageTestCase):
    def test_doctors_cannot_open_patient_pages(self):
        for url in ["/record/", "/privacy/", "/privacy/?tab=activity"]:
            self.assertEqual(self.doc.get(url).status_code, 302, url)
            self.assertEqual(self.doc.get(url)["Location"], "/dashboard/", url)

    def test_patients_cannot_open_doctor_pages(self):
        for url in ["/patients/", "/emergency/", "/patient/1001/", "/patient/1001/emergency/"]:
            self.assertEqual(self.pat.get(url).status_code, 302, url)
        self.pat.post("/request/1001/")
        self.pat.post("/patient/1001/consult/", {"notes": "x"})
        self.assertEqual((count("access_requests"), count("consultations")), (0, 0))
        self.assertEqual(self.pat.get("/patients/suggest/?q=juan").status_code, 403)

    def test_only_the_patient_who_owns_a_request_can_answer_or_revoke_it(self):
        request = approve(self.s)
        other = new_patient(self.s, "Other", PASSWORD, "M", BORN)
        other_client = login(other.user_id, PASSWORD)
        other_client.post(f"/revoke/{request.request_id}/")
        other_client.post(f"/respond/{request.request_id}/deny/")
        self.doc.post(f"/revoke/{request.request_id}/")
        self.assertEqual(self.s.access_status(2001, 1001), "approved")

    def test_an_answered_request_cannot_be_flipped_and_bad_ids_do_not_crash(self):
        request = approve(self.s)
        self.pat.post(f"/respond/{request.request_id}/deny/")
        self.assertEqual(self.s.access_status(2001, 1001), "approved")
        self.assertEqual(self.pat.post("/respond/99999/approve/").status_code, 302)
        self.assertEqual(self.pat.post("/revoke/99999/").status_code, 302)

    def test_redirects_only_go_to_known_pages(self):
        request = approve(self.s)
        r = self.pat.post(f"/revoke/{request.request_id}/", {"next": "https://evil.example"})
        self.assertEqual(r["Location"], "/dashboard/")
        approve_again = self.s.request_access(self.s.get_doctor(2001), 1001)
        r = self.pat.post(f"/respond/{approve_again.request_id}/approve/", {"next": "//evil.example"})
        self.assertEqual(r["Location"], "/dashboard/")
        r = self.pat.post(f"/revoke/{approve_again.request_id}/", {"next": "my_doctors"})   # a name from an older version
        self.assertEqual(r["Location"], "/dashboard/")


class NotificationPanel(PageTestCase):
    def test_the_badge_and_the_panel_show_new_messages(self):
        self.doc.post("/request/1001/")
        page = html(self.pat.get("/dashboard/"))
        self.assertIn('data-count="1"', page)
        self.assertIn("requests access to your record", page)
        self.assertIn("unread", page)

    def test_opening_the_panel_marks_everything_read_and_needs_the_csrf_token(self):
        self.doc.post("/request/1001/")
        strict = Client(enforce_csrf_checks=True)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html(strict.get("/"))).group(1)
        strict.post("/", {"user_id": "1001", "password": "pat123", "csrfmiddlewaretoken": token})
        self.assertEqual(strict.post("/notifications/read/").status_code, 403)
        self.assertEqual(self.s.unread_count(1001), 1)
        page = strict.get("/dashboard/")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html(page)).group(1)
        r = strict.post("/notifications/read/", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.s.unread_count(1001), 0)
        self.assertIn("hidden", html(strict.get("/dashboard/")).split('id="unread-badge"')[1][:90])

    def test_strangers_cannot_use_the_endpoint(self):
        self.assertEqual(Client().post("/notifications/read/").status_code, 403)
        self.assertEqual(self.pat.get("/notifications/read/").status_code, 403)


class NoLeaks(PageTestCase):
    def test_no_raw_template_tags_on_any_page(self):
        for client, urls in [(self.doc, DOCTOR_PAGES), (self.pat, PATIENT_PAGES),
                             (Client(), ["/", "/register/"])]:
            for url in urls:
                body = html(client.get(url))
                self.assertNotIn("{%", body, url)
                self.assertNotIn("{{", body, url)


if __name__ == "__main__":
    unittest.main()
