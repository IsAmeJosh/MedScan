"""The one-time QR code and what it brings: scans in the history, request times, notification kinds, contact numbers."""
import re
import unittest

from models.M_Access_Request import AccessRequest
from models.M_Notification import Notification
from models.M_QR_Code import QRCode
from models.M_QR_Token import QRToken
from models.M_Scan_Result import ScanResult
from tests.helpers import PASSWORD, approve, count, execute, fresh_system, html, login, rows

SECRET = "a" * 32


class TheModels(unittest.TestCase):
    """The new classes on their own, no database needed."""

    def test_a_token_counts_down_from_five_minutes_by_the_age_the_database_measured(self):
        self.assertEqual(QRToken(1, 1001, SECRET, 0).seconds_left, 300)
        self.assertEqual(QRToken(1, 1001, SECRET, 272).seconds_left, 28)
        self.assertEqual(QRToken(1, 1001, SECRET, 9999).seconds_left, 0)

    def test_the_secret_can_be_read_but_not_changed(self):
        token = QRToken(1, 1001, SECRET, 0)
        self.assertEqual(token.value, SECRET)
        with self.assertRaises(AttributeError):
            token.value = "b" * 32

    def test_new_secrets_are_32_hex_characters_and_never_repeat(self):
        values = {QRToken.make_value() for _ in range(200)}
        self.assertEqual(len(values), 200)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{32}", v) for v in values))

    def test_a_live_code_holds_the_id_and_the_secret_and_the_picture_hides_the_secret_in_its_title(self):
        code = QRCode.with_secret("PT-2026-01001", SECRET)
        self.assertEqual(code.text, f"PT-2026-01001:{SECRET}")
        self.assertIn("QR code for PT-2026-01001<", code.svg())
        self.assertNotIn(SECRET, code.svg())

    def test_reading_a_scan_gives_the_id_and_the_secret_if_there_is_one(self):
        self.assertEqual(QRCode.parse("PT-2026-01001"), (1001, None))
        self.assertEqual(QRCode.parse(f" PT-2026-01001:{SECRET}\n"), (1001, SECRET))
        for bad in ("PT-2026-01001:abc", f"PT-2026-01001:{SECRET.upper()}", f"DR-2026-02001:{SECRET}", "", None):
            self.assertEqual(QRCode.parse(bad), (None, None), bad)

    def test_a_request_remembers_when_it_was_asked_and_decided_and_how(self):
        request = AccessRequest(1, 2001, 1001)
        self.assertIsNone(request.decided_at)
        self.assertFalse(request.approved_by_qr)
        request.approve(via="qr")
        self.assertTrue(request.approved_by_qr)
        self.assertIsNotNone(request.decided_at)
        request.revoke()
        self.assertFalse(request.approved_by_qr)

    def test_a_notification_knows_where_it_leads(self):
        def where(kind, role="Patient"):
            return Notification(1, 1001, "x", kind=kind).destination(role)
        self.assertEqual((where("request"), where("note"), where("scan"), where("emergency")),
                         ("requests", "record", "history", "history"))
        self.assertEqual(where("approved", "Doctor"), "patients")

    def test_a_scan_result_opens_the_record_only_when_the_scan_approved_or_already_had_access(self):
        self.assertTrue(ScanResult(ScanResult.APPROVED, 1001).opens_record)
        self.assertTrue(ScanResult(ScanResult.ALREADY, 1001).opens_record)
        for outcome in (ScanResult.FOUND, ScanResult.EXPIRED, ScanResult.INVALID):
            self.assertFalse(ScanResult(outcome, 1001).opens_record, outcome)


class IssuingCodes(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_asking_twice_gives_the_same_code_until_it_is_replaced(self):
        first = self.s.current_qr(1001)
        self.assertEqual(self.s.current_qr(1001).token_id, first.token_id)
        self.assertGreater(first.seconds_left, 290)

    def test_a_new_code_replaces_the_old_one_at_once(self):
        old = self.s.current_qr(1001)
        new = self.s.new_qr(1001)
        self.assertNotEqual(old.value, new.value)
        self.assertEqual(self.s.current_qr(1001).token_id, new.token_id)
        self.assertEqual(count("tb_qr_tokens", "patient_id = 1001 AND spent_at IS NULL"), 1)

    def test_a_code_that_ran_out_of_time_is_replaced_by_a_fresh_one(self):
        old = self.s.current_qr(1001)
        execute("UPDATE tb_qr_tokens SET created_at = created_at - INTERVAL 6 MINUTE")
        fresh = self.s.current_qr(1001)
        self.assertNotEqual(fresh.token_id, old.token_id)
        self.assertGreater(fresh.seconds_left, 290)


class Scanning(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def live(self, patient_id=1001):
        """The text inside the patient's live QR code."""
        return self.s.get_patient(patient_id).qr_code(self.s.current_qr(patient_id)).text

    def test_a_live_code_approves_the_doctor_logs_the_scan_and_tells_the_patient(self):
        result = self.s.scan_qr(self.reyes, self.live())
        self.assertEqual((result.outcome, result.patient_id), (ScanResult.APPROVED, 1001))
        self.assertTrue(self.s.has_access(2001, 1001))
        (request,) = self.s.request_rows_for_doctor(2001)
        self.assertTrue(request[0].approved_by_qr)
        self.assertIsNotNone(request[0].decided_at)
        self.assertEqual(count("tb_qr_scans"), 1)
        (note,) = self.s.inbox(1001)
        self.assertEqual((note.kind, note.message), ("scan", "Dr. Reyes scanned your QR code."))
        self.assertIsNotNone(self.s.open_record(self.reyes, 1001))

    def test_a_code_works_only_once(self):
        text = self.live()
        self.assertEqual(self.s.scan_qr(self.reyes, text).outcome, ScanResult.APPROVED)
        santos = self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview")
        self.assertEqual(self.s.scan_qr(santos, text).outcome, ScanResult.EXPIRED)
        self.assertFalse(self.s.has_access(santos.user_id, 1001))

    def test_a_code_that_ran_out_of_time_approves_nobody(self):
        text = self.live()
        execute("UPDATE tb_qr_tokens SET created_at = created_at - INTERVAL 6 MINUTE")
        self.assertEqual(self.s.scan_qr(self.reyes, text).outcome, ScanResult.EXPIRED)
        self.assertFalse(self.s.has_access(2001, 1001))
        self.assertEqual(count("tb_qr_scans"), 0)

    def test_a_replaced_code_no_longer_works(self):
        old = self.live()
        self.s.new_qr(1001)
        self.assertEqual(self.s.scan_qr(self.reyes, old).outcome, ScanResult.EXPIRED)

    def test_another_patients_secret_on_this_patients_id_approves_nobody_and_uses_nothing_up(self):
        ana = self.s.register_patient("Ana Lopez", "ana123", "Female", "1998-02-01", contact_number="09281112222")
        anas = self.s.current_qr(ana.user_id)
        forged = f"PT-2026-01001:{anas.value}"
        self.assertEqual(self.s.scan_qr(self.reyes, forged).outcome, ScanResult.EXPIRED)
        self.assertFalse(self.s.has_access(2001, 1001))
        self.assertEqual(count("tb_qr_tokens", "patient_id = %s AND spent_at IS NULL", ana.user_id), 1)   # Ana's real code is untouched
        self.assertEqual(self.s.current_qr(ana.user_id).token_id, anas.token_id)

    def test_a_plain_id_code_only_finds_the_patient(self):
        result = self.s.scan_qr(self.reyes, "PT-2026-01001")
        self.assertEqual((result.outcome, result.patient_id), (ScanResult.FOUND, 1001))
        self.assertFalse(self.s.has_access(2001, 1001))
        self.assertEqual(count("tb_access_requests"), 0)
        self.assertEqual(count("tb_qr_scans"), 0)

    def test_anything_else_is_not_a_code(self):
        for text in ("https://example.com", "DR-2026-02001", "", None):
            self.assertEqual(self.s.scan_qr(self.reyes, text).outcome, ScanResult.INVALID, text)

    def test_a_doctor_who_already_had_access_is_logged_but_gets_no_second_request(self):
        approve(self.s)
        result = self.s.scan_qr(self.reyes, self.live())
        self.assertEqual(result.outcome, ScanResult.ALREADY)
        self.assertEqual(count("tb_access_requests"), 1)
        self.assertEqual(count("tb_qr_scans"), 1)

    def test_a_waiting_request_is_approved_by_the_scan_and_its_message_is_dealt_with(self):
        request = self.s.request_access(self.reyes, 1001)
        self.assertEqual(self.s.unread_count(1001), 1)
        self.s.scan_qr(self.reyes, self.live())
        (row,) = self.s.request_rows_for_doctor(2001)
        self.assertEqual((row[0].request_id, row[0].status, row[0].via), (request.request_id, "Approved", "qr"))
        self.assertEqual(count("tb_access_requests"), 1)
        kinds = {n.kind: n.is_read for n in self.s.inbox(1001)}
        self.assertTrue(kinds["request"])           # no longer waiting for an answer
        self.assertFalse(kinds["scan"])

    def test_taking_access_back_keeps_the_history_and_the_doctor_is_out(self):
        self.s.scan_qr(self.reyes, self.live())
        (row,) = self.s.request_rows_for_doctor(2001)
        self.assertTrue(self.s.revoke_access(row[0].request_id, 1001))
        self.assertFalse(self.s.has_access(2001, 1001))
        self.assertEqual(count("tb_qr_scans"), 1)


class HistoryAndKinds(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)

    def test_scans_are_in_the_history_with_their_own_chip(self):
        self.s.scan_qr(self.reyes, self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text)
        self.s.open_record(self.reyes, 1001)
        self.s.emergency_access(self.reyes, 1001, "Collapsed")
        items = self.s.activity_for_patient(1001)
        self.assertEqual(sorted(i["kind"] for i in items), ["override", "scan", "view"])
        self.assertEqual(self.s.activity_counts(items), {"all": 3, "scan": 1, "approved": 1, "emergency": 1})
        self.assertEqual([i["kind"] for i in self.s.filter_activity(items, "scan")], ["scan"])
        self.assertEqual(len(self.s.filter_activity(items, "nonsense")), 3)

    def test_every_message_has_the_kind_that_says_where_it_leads(self):
        request = self.s.request_access(self.reyes, 1001)
        self.s.respond_to_request(request.request_id, 1001, True)
        self.s.add_consultation(self.reyes, 1001, "Checkup")
        self.s.emergency_access(self.reyes, 1001, "Collapsed")
        self.s.revoke_access(request.request_id, 1001)
        patient = {n.kind for n in self.s.inbox(1001)}
        doctor = {n.kind for n in self.s.inbox(2001)}
        self.assertEqual(patient, {"request", "note", "emergency"})
        self.assertEqual(doctor, {"approved", "revoked"})
        denied = self.s.request_access(self.reyes, 1001)
        self.s.respond_to_request(denied.request_id, 1001, False)
        self.assertIn("denied", {n.kind for n in self.s.inbox(2001)})

    def test_requests_remember_when_they_were_asked_and_decided(self):
        request = self.s.request_access(self.reyes, 1001)
        row = self.s.request_rows_for_patient(1001)[0][0]
        self.assertIsNotNone(row.created_at)
        self.assertIsNone(row.decided_at)
        self.s.respond_to_request(request.request_id, 1001, True)
        row = self.s.request_rows_for_patient(1001)[0][0]
        self.assertEqual((row.status, row.via), ("Approved", "request"))
        self.assertIsNotNone(row.decided_at)


class ContactNumbers(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)

    def test_a_doctor_can_register_with_a_number_or_without(self):
        with_number = self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview", "+63 918 555 0000")
        self.assertEqual(with_number.contact_number, "09185550000")
        self.assertEqual(self.s.register_doctor("Liza Cruz", PASSWORD, "ER").contact_number, "")
        with self.assertRaises(ValueError):
            self.s.register_doctor("Bad Number", PASSWORD, "ER", "", "12")

    def test_the_demo_doctor_has_a_number_and_a_password_date(self):
        reyes = self.s.get_doctor(2001)
        self.assertEqual(reyes.contact_number, "09181112222")
        self.assertIsNotNone(reyes.password_changed_at)
        self.assertIsNotNone(self.s.get_patient(1001).password_changed_at)

    def test_a_doctor_can_change_and_clear_their_number(self):
        self.assertEqual(self.s.update_contact_number(2001, "0918 333 4444").contact_number, "09183334444")
        self.assertEqual(self.s.update_contact_number(2001, "").contact_number, "")
        with self.assertRaises(ValueError):
            self.s.update_contact_number(2001, "12")

    def test_a_patient_needs_a_number_and_it_must_be_theirs_alone(self):
        self.assertEqual(self.s.update_contact_number(1001, "0917 555 1234").contact_number, "09175551234")
        with self.assertRaises(ValueError):
            self.s.update_contact_number(1001, "")
        ana = self.s.register_patient("Ana Lopez", "ana123", "Female", "1998-02-01", contact_number="09281112222")
        with self.assertRaises(ValueError):
            self.s.update_contact_number(ana.user_id, "09175551234")
        self.assertEqual(self.s.get_patient(1001).contact_number, "09175551234")

    def test_nobody_is_not_a_user(self):
        self.assertIsNone(self.s.update_contact_number(999999, "09171234567"))


class ThePages(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.doc = login(2001, "doc123")
        self.pat = login(1001, "pat123")

    @staticmethod
    def main(response):
        """Only the page's own content (the notification panel is on every page and has its own words)."""
        return html(response).split('<main class="content')[1].split("</main>")[0]

    def scan(self, text=None):
        text = text or self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text
        return self.doc.get(f"/qr/scan/?code={text}", follow=True)

    def test_the_patient_gets_a_live_code_as_json_and_looking_does_not_keep_the_session_alive(self):
        r = self.pat.get("/qr/code/")
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["svg"].startswith("<svg"))
        self.assertTrue(290 < data["seconds"] <= 300)
        self.assertNotIn("sessionid", r.cookies)                      # a passive request, like the notification poll
        self.assertEqual(self.pat.get("/qr/code/").json()["id"], data["id"])

    def test_only_a_patient_gets_a_code(self):
        self.assertEqual(self.doc.get("/qr/code/").status_code, 403)
        self.assertEqual(self.doc.post("/qr/new/").status_code, 403)
        self.assertEqual(login(0, "x").get("/qr/code/").status_code, 403)

    def test_make_a_new_code_needs_a_post_and_replaces_the_code(self):
        first = self.pat.get("/qr/code/").json()
        self.assertEqual(self.pat.get("/qr/new/").status_code, 403)
        second = self.pat.post("/qr/new/").json()
        self.assertTrue(second["ok"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.pat.get("/qr/code/").json()["id"], second["id"])
        self.assertNotEqual(first["svg"], second["svg"])

    def test_the_sheet_has_the_timer_and_the_new_code_button(self):
        sheet = re.search(r'<dialog id="qr-sheet".*?</dialog>', html(self.pat.get("/dashboard/")), re.S).group(0)
        for part in ('data-code-url="/qr/code/"', 'data-new-url="/qr/new/"', 'id="qr-timer-text"', "Make a new code"):
            self.assertIn(part, sheet)
        self.assertIn("js/G_Qr.js", html(self.pat.get("/dashboard/")))

    def test_a_doctor_who_scans_a_live_code_lands_on_the_open_record_with_a_message(self):
        r = self.scan()
        self.assertEqual(r.redirect_chain[-1][0], "/patient/1001/")
        self.assertIn("Scan successful. Access approved and logged.", html(r))
        self.assertIn("Juan Dela Cruz", html(r))

    def test_a_used_code_goes_back_to_the_scanner_with_a_message(self):
        text = self.s.get_patient(1001).qr_code(self.s.current_qr(1001)).text
        self.scan(text)
        santos = self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview")
        r = login(santos.user_id, PASSWORD).get(f"/qr/scan/?code={text}", follow=True)
        self.assertEqual(r.redirect_chain[-1][0], "/qr/")
        self.assertIn("already used or has run out of time", html(r))
        self.assertFalse(self.s.has_access(santos.user_id, 1001))

    def test_a_doctor_who_already_has_access_and_scans_a_new_code_is_told_so(self):
        self.scan()
        self.s.new_qr(1001)
        r = self.scan()
        self.assertIn("Scan logged. You already had access.", html(r))
        self.assertEqual(count("tb_access_requests"), 1)

    def test_the_patient_sees_the_scan_everywhere_it_belongs(self):
        self.scan()
        history = self.main(self.pat.get("/access/?tab=history"))
        self.assertIn("scanned your QR code", history)
        self.assertIn('class="pill green">QR scan<', history)
        self.assertRegex(history, r"QR scan <em>1</em>")
        self.assertIn("scanned your QR code", self.main(self.pat.get("/access/?tab=history&show=scan")))
        self.assertNotIn("scanned your QR code", self.main(self.pat.get("/access/?tab=history&show=emergency")))
        self.assertIn("allowed by QR scan, ", self.main(self.pat.get("/access/?tab=doctors")))
        self.assertIn("scanned your QR code", self.main(self.pat.get("/dashboard/")))
        panel = re.search(r'<div id="notification-list">(.*?)<div class="dfoot">', html(self.pat.get("/dashboard/")), re.S).group(1)
        self.assertIn("Dr. Reyes scanned your QR code.", panel)
        self.assertIn("Opens Access &middot; History", panel)

    def test_a_request_shows_when_it_was_asked(self):
        self.s.request_access(self.s.get_doctor(2001), 1001)
        self.assertRegex(html(self.pat.get("/dashboard/")), r'class="when">Today, \d\d:\d\d')      # the time sits in the card's corner
        self.assertRegex(html(self.pat.get("/access/?tab=requests")), r'class="when">Today, \d\d:\d\d')

    def test_a_note_tells_the_patient_and_leads_to_my_record(self):
        approve(self.s)
        self.doc.post("/patient/1001/consult/", {"notes": "Follow-up: BP 130/85"})
        (note,) = [n for n in self.s.inbox(1001) if n.kind == "note"]
        panel = html(self.pat.get("/dashboard/"))
        self.assertIn("Dr. Reyes added a consultation note.", panel)
        self.assertIn("Opens My Record", panel)
        r = self.pat.get(f"/notifications/{note.notification_id}/open/")
        self.assertEqual((r.status_code, r["Location"]), (302, "/record/"))

    def test_the_profile_shows_the_contact_number_for_both_roles(self):
        patient = html(self.pat.get("/profile/"))
        self.assertIn("0917 123 4567", patient)
        doctor = html(self.doc.get("/profile/"))
        self.assertIn("Work details", doctor)
        self.assertIn("This month", doctor)
        self.assertIn("0918 111 2222", doctor)
        self.assertIn('data-sheet="edit-personal"', patient)
        self.assertIn('<dialog id="edit-personal"', patient)
        self.assertIn('data-sheet="edit-work"', doctor)
        self.assertIn('<dialog id="edit-work"', doctor)

    def test_editing_the_contact_number_from_the_profile(self):
        r = self.doc.post("/details/work/", {"contact_number": "0918 777 8888", "next": "/profile/"}, follow=True)
        self.assertIn("<span>Saved</span>", html(r))
        self.assertEqual(self.s.get_doctor(2001).contact_number, "09187778888")
        r = self.pat.post("/details/personal/", {"date_of_birth": "03/14/1996", "sex": "Male", "blood_type": "O+", "contact_number": "12", "next": "/profile/"}, follow=True)
        self.assertIn("Enter an 11-digit mobile number", html(r))
        self.assertEqual(self.s.get_patient(1001).contact_number, "09171234567")
        self.assertEqual(self.doc.get("/details/work/").status_code, 302)          # only a form can change it
        self.assertEqual(login(0, "x").post("/details/work/", {"contact_number": "0917"}).status_code, 302)


class Persisting(unittest.TestCase):
    def test_what_the_new_tables_hold_is_really_saved(self):
        s = fresh_system(self)
        reyes = s.get_doctor(2001)
        token = s.current_qr(1001)
        s.scan_qr(reyes, s.get_patient(1001).qr_code(token).text)
        self.assertEqual(rows("SELECT spent_at IS NOT NULL AS spent FROM tb_qr_tokens")[0]["spent"], 1)
        self.assertEqual(rows("SELECT via FROM tb_access_requests")[0]["via"], "qr")
        self.assertEqual(rows("SELECT kind FROM tb_notifications")[0]["kind"], "scan")


if __name__ == "__main__":
    unittest.main()
