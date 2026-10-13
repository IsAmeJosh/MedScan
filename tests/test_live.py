"""The bell and the sidebar counts update by themselves: the page asks /notifications/poll/ every few seconds.
(The JavaScript that does the asking is checked by hand, see README. These tests cover everything the server does.)"""
import re
import time
import unittest
from unittest import mock

from django.conf import settings
from django.test import Client

from tests.helpers import approve, count, fresh_system, html, login


class PageTestCase(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")
        self.doctor = self.s.get_doctor(2001)


class PollAnswers(PageTestCase):
    def test_a_patient_with_nothing_new(self):
        data = self.pat.get("/notifications/poll/").json()
        self.assertEqual((data["ok"], data["unread"], data["waiting"], data["latest"]), (True, 0, 0, ""))
        self.assertIn("all caught up", data["html"])
        self.assertNotIn("pending", data)

    def test_a_request_shows_up_in_the_patients_bell_and_sidebar_count(self):
        self.doc.post("/request/1001/")
        data = self.pat.get("/notifications/poll/").json()
        self.assertEqual((data["unread"], data["waiting"]), (1, 1))
        self.assertEqual(data["latest"], "Dr. Reyes requests access to your record.")
        self.assertRegex(data["html"], r'<div class="notice unread">\s*<a class="notice-main" href="/notifications/\d+/open/">')
        self.assertIn("requests access to your record", data["html"])

    def test_an_approval_shows_up_for_the_doctor_and_counts_as_ready_to_open(self):
        self.doc.post("/request/1001/")
        self.assertEqual(self.doc.get("/notifications/poll/").json()["ready"], 0)   # nothing to open yet
        request = self.s.request_rows_for_doctor(2001)[0][0]
        self.pat.post(f"/respond/{request.request_id}/approve/")
        data = self.doc.get("/notifications/poll/").json()
        self.assertEqual((data["unread"], data["ready"]), (1, 1))
        self.assertIn("Juan Dela Cruz approved your access request.", data["latest"])
        self.assertNotIn("waiting", data)
        self.doc.get("/patient/1001/")
        self.assertEqual(self.doc.get("/notifications/poll/").json()["ready"], 0)   # opened: no longer new

    def test_asking_does_not_mark_anything_read(self):
        self.doc.post("/request/1001/")
        for _ in range(3):
            self.pat.get("/notifications/poll/")
        self.assertEqual(self.s.unread_count(1001), 1)

    def test_everyone_only_sees_their_own_notifications(self):
        self.doc.post("/request/1001/")
        self.assertNotIn("requests access", self.doc.get("/notifications/poll/").json()["html"])
        self.assertEqual(self.doc.get("/notifications/poll/").json()["unread"], 0)

    def test_the_list_is_the_latest_twenty(self):
        for n in range(25):
            self.s.emergency_access(self.doctor, 1001, f"Reason {n}")
        data = self.pat.get("/notifications/poll/").json()
        self.assertEqual(data["unread"], 25)   # the badge counts them all
        self.assertEqual(len(re.findall(r'<div class="notice( unread)?">', data["html"])), 20)

    def test_anything_typed_into_a_message_is_escaped_before_it_reaches_the_page(self):
        self.s.emergency_access(self.doctor, 1001, "<script>alert(1)</script>")
        html_text = self.pat.get("/notifications/poll/").json()["html"]
        self.assertNotIn("<script>", html_text)
        self.assertIn("&lt;script&gt;", html_text)

    def test_strangers_and_ended_sessions_get_a_403(self):
        r = Client().get("/notifications/poll/")
        self.assertEqual((r.status_code, r.json()), (403, {"ok": False}))

    def test_the_answer_matches_what_a_fresh_page_would_show(self):
        self.doc.post("/request/1001/")
        live = self.pat.get("/notifications/poll/").json()["html"].strip()
        page = html(self.pat.get("/dashboard/"))
        panel = re.search(r'<div id="notification-list">(.*?)</div>\s*</aside>', page, re.S).group(1).strip()
        self.assertEqual(re.sub(r"\s+", " ", live), re.sub(r"\s+", " ", panel))


class PageIsReadyForLiveUpdates(PageTestCase):
    def test_the_panel_knows_where_to_ask_and_how_often(self):
        page = html(self.pat.get("/dashboard/"))
        self.assertIn('data-poll-url="/notifications/poll/"', page)
        self.assertIn('data-poll-seconds="10"', page)
        self.assertEqual(settings.NOTIFICATION_POLL_SECONDS, 10)
        self.assertIn('id="notification-list"', page)

    def test_the_counts_are_always_on_the_page_hidden_when_zero(self):
        patient = html(self.pat.get("/dashboard/"))
        self.assertRegex(patient, r'id="count-waiting" hidden>0<')
        self.assertRegex(patient, r'id="new-count" hidden>0 new<')
        self.assertRegex(patient, r'id="mark-all-read" hidden>')
        doctor = html(self.doc.get("/dashboard/"))
        self.assertRegex(doctor, r'id="count-ready" hidden>0<')

    def test_the_counts_show_when_there_is_something(self):
        self.doc.post("/request/1001/")
        patient = html(self.pat.get("/dashboard/"))
        self.assertRegex(patient, r'id="count-waiting" >1<')
        self.assertRegex(patient, r'id="new-count" >1 new<')
        request = self.s.request_rows_for_doctor(2001)[0][0]
        self.s.respond_to_request(request.request_id, 1001, True)
        self.assertRegex(html(self.doc.get("/dashboard/")), r'id="count-ready" >1<')

    def test_the_login_page_does_not_ask(self):
        self.assertNotIn("poll", html(Client().get("/")))


class AskingIsNotActivity(PageTestCase):
    """The idle logout must still work in a tab that is only asking for notifications."""

    def test_the_answer_does_not_renew_the_session_cookie_but_a_page_does(self):
        client = Client()
        client.post("/", {"user_id": "1001", "password": "pat123"})
        self.assertNotIn("sessionid", client.get("/notifications/poll/").cookies)
        self.assertIn("sessionid", client.get("/dashboard/").cookies)

    def test_a_tab_that_only_asks_still_gets_logged_out_after_15_minutes(self):
        start = time.time()
        client = login(1001, "pat123")
        with mock.patch("django.core.signing.time.time", return_value=start + 14 * 60):
            self.assertEqual(client.get("/notifications/poll/").status_code, 200)   # asking at 14 minutes
        with mock.patch("django.core.signing.time.time", return_value=start + 16 * 60):
            self.assertEqual(client.get("/notifications/poll/").status_code, 403)   # nothing renewed it
            r = client.get("/dashboard/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/"))

    def test_a_real_page_at_14_minutes_does_keep_the_session_alive(self):
        start = time.time()
        client = login(1001, "pat123")
        with mock.patch("django.core.signing.time.time", return_value=start + 14 * 60):
            self.assertEqual(client.get("/dashboard/").status_code, 200)
        with mock.patch("django.core.signing.time.time", return_value=start + 16 * 60):
            self.assertEqual(client.get("/dashboard/").status_code, 200)

    def test_the_keepalive_still_renews_it(self):
        client = Client()
        client.post("/", {"user_id": "1001", "password": "pat123"})
        self.assertIn("sessionid", client.post("/keepalive/").cookies)


class NothingIsWritten(PageTestCase):
    def test_asking_changes_nothing_in_the_database(self):
        approve(self.s)
        before = (count("notifications"), count("record_views"), count("access_requests"))
        for _ in range(5):
            self.pat.get("/notifications/poll/")
            self.doc.get("/notifications/poll/")
        self.assertEqual((count("notifications"), count("record_views"), count("access_requests")), before)


if __name__ == "__main__":
    unittest.main()
