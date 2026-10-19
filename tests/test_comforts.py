"""Comforts: typing helpers, messages and pop-ups, clickable notifications, filters and pages, idle logout.
(The JavaScript that makes these work in the browser is tested in test_javascript.py. These tests check what the
server sends: the markup the scripts hook onto, and every rule that lives on the server.)"""
import re
import unittest
from datetime import date
from unittest import mock

from django.conf import settings
from django.test import Client

from gui.G_Filters import mobile
from tests.helpers import (BORN, PASSWORD, approve, count, execute, fresh_system, html, login, rows)
from tests.helpers import new_patient, next_mobile


class PageTestCase(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")


def listed_patients(page):
    """The patient names in the page's list (not the ones that also appear in the notification panel)."""
    return re.findall(r'<div class="g">\s*<b>(Patient \d\d)</b>', page)


def input_tag(page, name):
    """The <input ...> text for the field with this name."""
    return re.search(r"<input[^>]*name=\"%s\"[^>]*>" % name, page, re.S).group(0)


class MobileNumbersOnScreen(PageTestCase):
    def test_the_filter_spaces_a_saved_number_and_leaves_everything_else_alone(self):
        self.assertEqual(mobile("09171234567"), "0917 123 4567")
        for other in ["", None, "123", "0917 123 4567", "0917123456a"]:
            self.assertEqual(mobile(other), other)

    def test_every_page_shows_the_same_spaced_format(self):
        page = html(self.pat.get("/record/"))
        self.assertIn("0917 123 4567", page)
        self.assertNotIn("09171234567", page)
        approve(self.s)
        page = html(self.doc.get("/patient/1001/"))
        self.assertIn("0917 123 4567", page)
        self.assertNotIn("09171234567", page)

    def test_the_edit_form_starts_with_the_spaced_number_and_the_typing_helper(self):
        tag = input_tag(html(self.pat.get("/record/")), "contact_number")
        self.assertIn('value="0917 123 4567"', tag)
        self.assertIn('data-format="mobile"', tag)
        self.assertIn('data-validate="mobile-required"', tag)

    def test_a_number_typed_in_the_spaced_style_is_saved_without_spaces(self):
        self.pat.post("/record/edit/", {"contact_number": "0928 111 2222"})
        self.assertEqual(rows("SELECT mobile_number FROM tb_patients WHERE patient_id = 1001")[0]["mobile_number"],
                         "09281112222")


class DateOfBirthTyping(PageTestCase):
    def register(self, born):
        return Client().post("/register/", {"role": "Patient", "name": "Zed", "password": PASSWORD,
                                            "date_of_birth": born, "contact_number": next_mobile()}, follow=True)

    def test_the_server_accepts_what_the_form_produces(self):
        for typed in ["04/04/2004", "4/4/2004", "2004-04-04"]:
            r = self.register(typed)
            self.assertIn("Your MedScan ID is ready", html(r), typed)
        saved = rows("SELECT date_of_birth FROM tb_patients ORDER BY patient_id DESC LIMIT 3")
        self.assertEqual({row["date_of_birth"] for row in saved}, {date(2004, 4, 4)})

    def test_two_digit_years_and_impossible_dates_are_refused_with_the_format_shown(self):
        before = count("tb_patients")
        for typed in ["04/04/04", "13/01/2004", "02/30/2004", "2004/04/04", "04042004"]:
            self.assertIn("like 04/04/2004", html(self.register(typed)), typed)
        self.assertEqual(count("tb_patients"), before)

    def test_the_visible_date_box_is_plain_text_not_the_browsers_date_control(self):
        page = html(Client().get("/register/?role=patient"))
        tag = input_tag(page, "date_of_birth")
        self.assertNotIn('type="date"', tag)
        self.assertIn('data-format="date"', tag)
        self.assertIn('inputmode="numeric"', tag)
        self.assertIn('placeholder="MM/DD/YYYY"', tag)
        self.assertIn("data-date-picker", page)   # the optional calendar button
        self.assertIn('class="date-native"', page)

    def test_a_wrong_date_comes_back_as_typed_so_it_can_be_fixed(self):
        self.assertIn('value="04/04/04"', html(self.register("04/04/04")))


class RegistrationHelpers(PageTestCase):
    def setUp(self):
        super().setUp()
        self.page = html(Client().get("/register/?role=patient"))

    def test_the_form_is_wired_for_live_checking(self):
        self.assertIn("data-validate-form", self.page)
        self.assertIn("data-submit", self.page)
        self.assertIn("data-submit-hint", self.page)

    def test_password_has_the_limits_a_show_word_and_a_caps_warning_and_no_counter(self):
        tag = input_tag(self.page, "password")
        self.assertNotIn("data-counter", tag)                            # the design has no counter under the box
        for hook in ['data-min="6"', 'minlength="6"', 'maxlength="25"', 'data-toggle-password',
                     'data-validate="password"', 'autocomplete="new-password"']:
            self.assertIn(hook, tag)
        self.assertIn('class="pw-eye"', self.page)
        self.assertIn('<span class="eye-on">Show</span><span class="eye-off">Hide</span>', self.page)
        self.assertIn("Caps Lock is on", self.page)

    def test_the_other_fields_have_their_rules_and_no_counters(self):
        self.assertNotIn("data-counter", input_tag(self.page, "name"))
        self.assertIn('data-validate="name"', input_tag(self.page, "name"))
        doctor = html(Client().get("/register/?role=doctor"))
        self.assertNotIn("data-counter", input_tag(doctor, "specialty"))
        self.assertNotIn("data-counter", input_tag(doctor, "clinic"))

    def test_medical_history_uses_chips(self):
        self.assertIn("data-chips", input_tag(self.page, "allergies"))
        self.assertIn("data-chips", input_tag(self.page, "surgeries"))

    def test_the_scripts_are_loaded_and_exist(self):
        for script in ["G_Format.js", "G_Fields.js", "G_Chips.js", "G_Dialogs.js"]:
            self.assertIn(f"js/{script}", self.page)

    def test_the_login_form_has_the_eye_and_the_caps_warning_too(self):
        page = html(Client().get("/"))
        self.assertIn("data-toggle-password", page)
        self.assertIn('class="pw-eye"', page)
        self.assertIn("Caps Lock is on", page)

    def test_the_edit_form_has_chips_for_all_three_lists(self):
        page = html(self.pat.get("/record/"))
        for name in ["allergies", "medications", "surgeries"]:
            self.assertIn("data-chips", input_tag(page, name))

    def test_the_chips_start_from_what_is_saved(self):
        page = html(self.pat.get("/record/"))
        self.assertIn('value="Penicillin"', input_tag(page, "allergies"))
        self.assertIn('value="Appendectomy"', input_tag(page, "surgeries"))

    def test_chip_text_is_submitted_the_same_way_as_before(self):
        self.pat.post("/record/edit/", {"allergies": "Peanuts, Latex, penicillin", "medications": "Metformin, Metformin",
                                        "surgeries": "", "blood_type": "O+", "contact_number": "09171234567"})
        record = self.s.get_patient(1001).record
        self.assertEqual(record.allergies, ["Peanuts", "Latex", "penicillin"])
        self.assertEqual(record.medications, ["Metformin"])   # repeats are dropped


class Counters(PageTestCase):
    def test_the_emergency_reason_has_a_counter_and_the_note_box_has_none_as_in_the_design(self):
        approve(self.s)
        self.assertNotIn("data-counter", html(self.doc.get("/patient/1001/")))
        page = html(self.doc.get("/emergency/"))
        self.assertIn("data-counter", re.search(r"<textarea[^>]*name=\"reason\"[^>]*>", page).group(0))


class Messages(PageTestCase):
    def test_success_messages_are_the_teal_toast_without_a_close_button_and_errors_keep_theirs(self):
        r = self.pat.post("/record/edit/", {"allergies": "Peanuts", "contact_number": "09171234567"}, follow=True)
        page = html(r)
        self.assertIn('class="toast success"', page)
        self.assertIn("Your information was updated.", page)
        self.assertNotIn("toast-x", page)

    def test_errors_are_toasts_too_with_a_close_button(self):
        r = self.pat.post("/record/edit/", {"contact_number": "12"}, follow=True)
        self.assertIn('class="toast error"', html(r))
        self.assertIn("toast-x", html(r))

    def test_on_the_login_and_register_pages_errors_stay_next_to_the_form(self):
        page = html(Client().post("/", {"user_id": "2001", "password": "wrong"}))
        self.assertIn('class="alert red auth-alert"', page)
        self.assertNotIn('class="toast', page)
        page = html(Client().post("/register/", {"role": "Patient", "name": "Z", "password": "abc", "date_of_birth": BORN}))
        self.assertIn('class="alert red auth-alert"', page)

    def test_a_message_shows_once(self):
        self.pat.post("/record/edit/", {"allergies": "Peanuts", "contact_number": "09171234567"})
        self.assertIn("toast success", html(self.pat.get("/dashboard/")))
        self.assertNotIn("toast success", html(self.pat.get("/dashboard/")))


class ConfirmDialogs(PageTestCase):
    def test_the_dialog_is_on_logged_in_pages_only(self):
        self.assertIn('id="confirm-dialog"', html(self.pat.get("/dashboard/")))
        self.assertNotIn('id="confirm-dialog"', html(Client().get("/")))

    def test_revoking_asks_first(self):
        approve(self.s)
        form = re.search(r"<form[^>]*action=\"/revoke/\d+/\"[^>]*>", html(self.pat.get("/access/?tab=doctors"))).group(0)
        self.assertIn("data-confirm=", form)
        self.assertIn('data-confirm-button="Remove access"', form)
        self.assertIn("Dr. Reyes will lose access", form)

    def test_denying_asks_first_on_home_and_on_access(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        for url in ["/dashboard/", "/access/?tab=requests"]:
            form = re.search(r"<form[^>]*action=\"/respond/\d+/deny/\"[^>]*>", html(self.pat.get(url))).group(0)
            self.assertIn("data-confirm=", form, url)
            self.assertIn("will be told you said no", form, url)

    def test_the_deny_button_in_the_review_sheet_asks_too_and_approve_does_not(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        sheet = re.search(r'<dialog id="review-\d+".*?</dialog>', html(self.pat.get("/dashboard/")), re.S).group(0)
        deny = re.search(r"<form[^>]*action=\"/respond/\d+/deny/\"[^>]*>", sheet).group(0)
        approve_form = re.search(r"<form[^>]*action=\"/respond/\d+/approve/\"[^>]*>", sheet).group(0)
        self.assertIn("data-confirm=", deny)
        self.assertNotIn("data-confirm", approve_form)

    def test_approving_does_not_ask(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        form = re.search(r"<form[^>]*action=\"/respond/\d+/approve/\"[^>]*>", html(self.pat.get("/dashboard/"))).group(0)
        self.assertNotIn("data-confirm", form)

    def test_the_emergency_page_asks_first_and_the_sheet_is_itself_the_question(self):
        form = re.search(r"<form[^>]*data-confirm=[^>]*>", html(self.doc.get("/emergency/"))).group(0)
        self.assertIn('data-confirm-tone="danger"', form)
        self.assertIn("without the patient", form)
        sheet = re.search(r'<dialog id="emergency-sheet".*?<form[^>]*>', html(self.doc.get("/patient/1001/")), re.S).group(0)
        self.assertNotIn("data-confirm", sheet)   # asking "are you sure" inside a sheet that says it already would be silly

    def test_the_actions_still_work_when_the_question_is_answered_yes(self):
        approve_request = approve(self.s)
        self.pat.post(f"/revoke/{approve_request.request_id}/")
        self.assertEqual(self.s.access_status(2001, 1001), "revoked")


class ClickableNotifications(PageTestCase):
    def test_each_notification_is_a_link_and_the_panel_has_mark_all_read(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        page = html(self.pat.get("/dashboard/"))
        self.assertRegex(page, r'<a class="row note unread" href="/notifications/\d+/open/">')
        self.assertIn("Opens Access &middot; Requests", page)
        self.assertIn('id="mark-all-read" >', page)
        self.assertIn('id="new-count" >', page)

    def test_the_button_and_count_are_hidden_when_there_is_nothing_new(self):
        page = html(self.pat.get("/dashboard/"))
        self.assertIn('id="mark-all-read" hidden', page)   # there, but hidden, so a new message can show it
        self.assertIn('id="new-count" hidden', page)
        self.assertIn("all caught up", page)

    def test_looking_at_the_panel_does_not_mark_anything_read(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        self.pat.get("/dashboard/")
        self.pat.get("/dashboard/")
        self.assertEqual(self.s.unread_count(1001), 1)

    def test_a_patients_request_notification_opens_access_requests_and_only_that_one_is_marked(self):
        doctor = self.s.get_doctor(2001)
        self.s.request_access(doctor, 1001)
        self.s.emergency_access(doctor, 1001, "Collapsed")
        first, second = sorted(n.notification_id for n in self.s.inbox(1001))
        r = self.pat.get(f"/notifications/{first}/open/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/access/?tab=requests"))
        self.assertEqual(self.s.unread_count(1001), 1)

    def test_an_emergency_alert_opens_the_history_tab(self):
        self.s.emergency_access(self.s.get_doctor(2001), 1001, "Collapsed")
        (note,) = self.s.inbox(1001)
        r = self.pat.get(f"/notifications/{note.notification_id}/open/")
        self.assertEqual(r["Location"], "/access/?tab=history")

    def test_a_doctors_approval_notification_opens_the_record_itself(self):
        request = self.s.request_access(self.s.get_doctor(2001), 1001)
        self.s.respond_to_request(request.request_id, 1001, True)
        (note,) = self.s.inbox(2001)
        r = self.doc.get(f"/notifications/{note.notification_id}/open/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/patient/1001/"))
        self.assertEqual(self.doc.get(r["Location"]).status_code, 200)
        self.assertEqual(self.s.unread_count(2001), 0)

    def test_a_doctors_denial_or_revoke_notification_opens_the_ended_tab(self):
        request = self.s.request_access(self.s.get_doctor(2001), 1001)
        self.s.respond_to_request(request.request_id, 1001, False)
        (note,) = self.s.inbox(2001)
        self.assertEqual(self.doc.get(f"/notifications/{note.notification_id}/open/")["Location"], "/patients/?show=denied")

    def test_an_approval_that_was_taken_back_does_not_open_a_locked_record(self):
        request = approve(self.s)
        self.s.revoke_access(request.request_id, 1001)
        approval = [n for n in self.s.inbox(2001) if "approved" in n.message][0]
        self.assertEqual(self.doc.get(f"/notifications/{approval.notification_id}/open/")["Location"], "/patients/?show=denied")

    def test_nobody_can_open_or_mark_someone_elses_notification(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        (note,) = self.s.inbox(1001)
        r = self.doc.get(f"/notifications/{note.notification_id}/open/")
        self.assertEqual(r["Location"], "/dashboard/")
        self.assertEqual(self.s.unread_count(1001), 1)

    def test_unknown_ids_and_strangers_are_handled(self):
        self.assertEqual(self.pat.get("/notifications/999999/open/")["Location"], "/dashboard/")
        self.assertEqual(Client().get("/notifications/1/open/")["Location"], "/")

    def test_mark_all_read_still_works_through_the_endpoint(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        self.assertEqual(self.pat.post("/notifications/read/").status_code, 200)
        self.assertEqual(self.s.unread_count(1001), 0)


class AnsweringRequests(PageTestCase):
    """The bell panel only points to Access. Approve and Deny are forms on Home, Access and the Review sheet."""
    def setUp(self):
        super().setUp()
        self.request = self.s.request_access(self.s.get_doctor(2001), 1001)

    def panel(self, client):
        return html(client.get("/dashboard/"))

    def test_a_waiting_request_has_deny_and_review_on_home_and_access_but_no_buttons_in_the_panel(self):
        for url in ["/dashboard/", "/access/?tab=requests"]:
            page = html(self.pat.get(url))
            self.assertIn(f'action="/respond/{self.request.request_id}/deny/"', page, url)
            self.assertIn(f'data-sheet="review-{self.request.request_id}"', page, url)
            self.assertIn(f'<dialog id="review-{self.request.request_id}"', page, url)
        panel = re.search(r'<div id="notification-list">(.*?)<div class="dfoot">', self.panel(self.pat), re.S).group(1)
        self.assertNotIn("<button", panel)
        self.assertNotIn("data-request-action", panel)

    def test_doctors_never_get_the_buttons(self):
        self.s.respond_to_request(self.request.request_id, 1001, True)
        self.assertNotIn("data-request-action", self.panel(self.doc))

    def test_a_request_that_was_answered_has_no_buttons_any_more(self):
        self.s.respond_to_request(self.request.request_id, 1001, False)
        self.assertNotIn("data-request-action", self.panel(self.pat))

    def test_other_notifications_never_have_buttons(self):
        self.s.emergency_access(self.s.get_doctor(2001), 1001, "Collapsed")
        page = self.panel(self.pat)
        self.assertEqual(page.count("data-request-action"), 0)   # the panel never has answer buttons

    def test_approving_goes_back_with_a_message_and_lets_the_doctor_in(self):
        r = self.pat.post(f"/respond/{self.request.request_id}/approve/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/dashboard/"))
        self.assertEqual(self.s.access_status(2001, 1001), "approved")
        page = html(self.pat.get("/dashboard/"))
        self.assertIn("Allowed. Dr. Reyes can now see your record.", page)
        self.assertIn('class="toast undo success"', page)
        self.assertIn('<a href="#">Undo</a>', page)                    # a demo placeholder, it only looks like a link

    def test_denying_goes_back_with_a_message_and_keeps_the_doctor_out(self):
        r = self.pat.post(f"/respond/{self.request.request_id}/deny/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.s.access_status(2001, 1001), "denied")
        page = html(self.pat.get("/dashboard/"))
        self.assertIn("Request declined.", page)
        self.assertNotIn("Undo", page)

    def test_answering_marks_that_notification_read_and_tells_the_doctor(self):
        self.pat.post(f"/respond/{self.request.request_id}/approve/")
        self.assertEqual(self.s.unread_count(1001), 0)
        self.assertTrue(any("Juan Dela Cruz approved" in n.message for n in self.s.inbox(2001)))

    def test_an_ordinary_form_answer_marks_it_read_too(self):
        self.pat.post(f"/respond/{self.request.request_id}/deny/")
        self.assertEqual(self.s.unread_count(1001), 0)

    def test_other_notifications_stay_unread_when_one_request_is_answered(self):
        self.s.emergency_access(self.s.get_doctor(2001), 1001, "Collapsed")
        self.pat.post(f"/respond/{self.request.request_id}/approve/")
        self.assertEqual(self.s.unread_count(1001), 1)   # the emergency alert

    def test_answering_twice_or_someone_elses_request_changes_nothing(self):
        self.pat.post(f"/respond/{self.request.request_id}/approve/")
        self.pat.post(f"/respond/{self.request.request_id}/deny/")                 # too late: it was already answered
        self.assertEqual(self.s.access_status(2001, 1001), "approved")
        other = new_patient(self.s, "Other", PASSWORD, "M", BORN)
        stranger = login(other.user_id, PASSWORD)
        stranger.post(f"/respond/{self.request.request_id}/deny/")                 # not their request
        self.assertEqual(self.s.access_status(2001, 1001), "approved")
        self.assertEqual(count("tb_access_requests", "status = 'Approved'"), 1)

    def test_doctors_and_strangers_can_not_answer_for_a_patient(self):
        for client in [self.doc, Client()]:
            client.post(f"/respond/{self.request.request_id}/approve/")
        self.assertEqual(self.s.access_status(2001, 1001), "pending")

    def test_a_get_does_not_answer_anything(self):
        self.pat.get(f"/respond/{self.request.request_id}/approve/")
        self.assertEqual(self.s.access_status(2001, 1001), "pending")


def listed_patients(page):
    """The patient names in the page's list (not the ones that also appear in the notification panel)."""
    return re.findall(r'<div class="g">\s*<b>(Patient \d\d)</b>', page)


class PatientListPages(PageTestCase):
    def make_requests(self, how_many):
        doctor = self.s.get_doctor(2001)
        for n in range(how_many):
            patient = new_patient(self.s, f"Patient {n:02d}", PASSWORD, "F", BORN)
            self.s.request_access(doctor, patient.user_id)

    def test_long_lists_are_split_into_pages_of_ten_and_keep_the_chip(self):
        self.make_requests(12)
        first = html(self.doc.get("/patients/?show=waiting"))
        self.assertEqual(len(listed_patients(first)), 10)
        self.assertIn("Showing 1&ndash;10 of 12", first)
        self.assertIn("Page 1 of 2", first)
        self.assertIn("?show=waiting&amp;page=2", first)
        second = html(self.doc.get("/patients/?show=waiting&page=2"))
        self.assertEqual(listed_patients(second), ["Patient 01", "Patient 00"])
        self.assertIn("Previous", second)
        self.assertNotIn("Next", second)

    def test_odd_page_numbers_do_not_crash(self):
        self.make_requests(3)
        for page in ["0", "-1", "abc", "999", ""]:
            self.assertEqual(self.doc.get(f"/patients/?show=waiting&page={page}").status_code, 200, page)

    def test_a_short_list_has_no_page_links(self):
        self.make_requests(3)
        self.assertNotIn('class="pager"', html(self.doc.get("/patients/?show=waiting")))

    def test_each_chip_has_its_own_empty_message(self):
        self.assertIn("No patients yet", html(self.doc.get("/patients/")))
        self.assertIn("No patient has approved you yet", html(self.doc.get("/patients/?show=access")))
        self.assertIn("A request you send stays here", html(self.doc.get("/patients/?show=waiting")))
        self.assertIn("You have not used emergency access", html(self.doc.get("/patients/?show=emergency")))
        self.assertIn("denied or taken back", html(self.doc.get("/patients/?show=denied")))


class ActivityPages(PageTestCase):
    def test_the_activity_tab_is_paged_and_shows_the_real_total(self):
        for _ in range(12):
            execute("INSERT INTO tb_record_views (doctor_id, patient_id, via) VALUES (2001, 1001, 'approved')")
        first = html(self.pat.get("/access/?tab=history"))
        self.assertEqual(first.count("Dr. Reyes opened your record"), 10)
        self.assertIn("Showing 1&ndash;10 of 12", first)
        self.assertRegex(first, r"All <em>12</em>")
        self.assertEqual(html(self.pat.get("/access/?tab=history&page=2")).count("Dr. Reyes opened your record"), 2)

    def test_emergency_uses_are_in_the_same_feed_with_their_reasons(self):
        doctor = self.s.get_doctor(2001)
        for n in range(3):
            self.s.emergency_access(doctor, 1001, f"Reason number {n}")
        page = html(self.pat.get("/access/?tab=history"))
        self.assertEqual(len(re.findall(r"Reason: Reason number \d", page)), 3)
        self.assertEqual(page.count("used emergency access"), 3)


class EmptyStates(PageTestCase):
    def test_the_messages_tell_people_what_to_do(self):
        self.assertIn("Nobody has opened your record yet", html(self.pat.get("/dashboard/")))
        access = html(self.pat.get("/access/"))
        self.assertIn("give a doctor your ID", access)
        self.assertIn(self.s.get_patient(1001).display_id, access)
        self.assertIn("all caught up", html(self.pat.get("/dashboard/")))   # the bell panel
        self.assertIn("Nobody yet. Scan a patient's code", html(self.doc.get("/dashboard/")).replace("&#x27;", "'"))


class IdleLogout(PageTestCase):
    def test_the_settings(self):
        self.assertEqual(settings.IDLE_LOGOUT_MINUTES, 15)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 15 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_logged_in_pages_carry_what_the_timer_needs(self):
        page = html(self.pat.get("/dashboard/"))
        for hook in ['data-idle-minutes="15"', 'data-keepalive-url="/keepalive/"', 'data-logout-url="/logout/"',
                     'data-login-url="/"', 'id="idle-dialog"', 'id="idle-stay"', 'js/G_Idle.js']:
            self.assertIn(hook, page)

    def test_the_login_page_has_no_timer(self):
        page = html(Client().get("/"))
        self.assertNotIn("data-idle-minutes", page)
        self.assertNotIn("G_Idle.js", page)

    def test_keepalive_answers_only_logged_in_posts(self):
        r = self.pat.post("/keepalive/")
        self.assertEqual((r.status_code, r.json()), (200, {"ok": True}))
        self.assertEqual(self.pat.get("/keepalive/").status_code, 403)
        self.assertEqual(Client().post("/keepalive/").status_code, 403)

    def test_the_login_page_explains_an_idle_logout(self):
        self.assertIn("after 15 minutes without activity", html(Client().get("/?expired=1")))
        self.assertNotIn("without activity", html(Client().get("/")))

    def test_the_session_cookie_lasts_15_minutes_and_is_renewed_by_every_page(self):
        client = Client()
        r = client.post("/", {"user_id": "1001", "password": "pat123"})
        self.assertEqual(r.cookies["sessionid"]["max-age"], 900)
        r = client.get("/dashboard/")
        self.assertIn("sessionid", r.cookies)   # a fresh cookie, so the 15 minutes start again

    def test_a_session_really_ends_after_15_minutes_without_a_page(self):
        import time
        now = time.time()
        client = login(1001, "pat123")
        with mock.patch("django.core.signing.time.time", return_value=now + 899):
            self.assertEqual(client.get("/dashboard/").status_code, 200)
        client = login(1001, "pat123")
        with mock.patch("django.core.signing.time.time", return_value=now + 901):
            r = client.get("/dashboard/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/"))


if __name__ == "__main__":
    unittest.main()
