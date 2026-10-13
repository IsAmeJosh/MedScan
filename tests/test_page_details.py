"""Details of the current pages: the doctor's clinic, Privacy (doctors and activity), Patients, Home."""
import unittest

from django.test import Client

from tests.helpers import PASSWORD, approve, fresh_system, rows


def login(uid, pw):
    c = Client()
    c.post("/", {"user_id": str(uid), "password": pw})
    return c


class GuiV2(unittest.TestCase):
    def setUp(self):
        self.s = fresh_system(self)
        self.reyes = self.s.get_doctor(2001)
        self.santos = self.s.register_doctor("Antonio Santos", PASSWORD, "Cardiology", "Northview Medical Center")
        self.lim = self.s.register_doctor("Jose Lim", PASSWORD, "Dermatology")

    def test_doctor_clinic_and_workplace(self):
        self.assertEqual(self.reyes.clinic, "Bayanihan Family Clinic")
        self.assertEqual(self.santos.workplace, "Cardiology at Northview Medical Center")
        self.assertEqual(self.lim.workplace, "Dermatology")  # no clinic given
        Client().post("/register/", {"role": "Doctor", "name": "Cruz", "password": PASSWORD,
                                     "specialty": "ENT", "clinic": "  Rizal Clinic "})
        cruz = self.s.get_doctor(rows("SELECT MAX(user_id) AS id FROM doctors")[0]["id"])
        self.assertEqual((cruz.name, cruz.clinic), ("Cruz", "Rizal Clinic"))

    def test_doctor_groups_one_row_per_doctor(self):
        s = self.s
        r1 = s.request_access(self.reyes, 1001); s.respond_to_request(r1.request_id, 1001, True)
        r2 = s.request_access(self.santos, 1001)
        r3 = s.request_access(self.lim, 1001); s.respond_to_request(r3.request_id, 1001, True)
        s.revoke_access(r3.request_id, 1001)
        s.open_record(self.reyes, 1001)
        groups = s.doctor_groups_for_patient(1001)
        self.assertEqual([d.name for _, d, _ in groups["with_access"]], ["Reyes"])
        self.assertEqual([d.name for _, d, _ in groups["waiting"]], ["Antonio Santos"])
        self.assertEqual([d.name for _, d, _ in groups["past"]], ["Jose Lim"])
        self.assertIsNotNone(groups["with_access"][0][2])  # Reyes viewed the record
        # Lim asks again: he moves from past to waiting, and is not listed twice
        s.request_access(self.lim, 1001)
        groups = s.doctor_groups_for_patient(1001)
        self.assertEqual(sorted(d.name for _, d, _ in groups["waiting"]), ["Antonio Santos", "Jose Lim"])
        self.assertEqual(groups["past"], [])
        self.assertEqual(s.pending_count_for_patient(1001), 2)

    def test_privacy_page_lists_doctors_with_their_clinics_and_takes_answers(self):
        s = self.s
        r1 = s.request_access(self.reyes, 1001); s.respond_to_request(r1.request_id, 1001, True)
        r2 = s.request_access(self.santos, 1001)
        pat = login(1001, "pat123")
        page = pat.get("/privacy/").content.decode()
        self.assertIn("Doctor in <b>General Medicine</b> at <b>Bayanihan Family Clinic</b>", page)
        self.assertIn("Doctor in <b>Cardiology</b> at <b>Northview Medical Center</b>", page)
        self.assertIn("Waiting for your answer", page)
        self.assertIn("Revoke access", page)
        r = pat.post(f"/respond/{r2.request_id}/approve/", {"next": "privacy"})
        self.assertEqual((r.status_code, r["Location"]), (302, "/privacy/"))
        self.assertTrue(s.has_access(self.santos.user_id, 1001))
        r = pat.post(f"/revoke/{r1.request_id}/", {"next": "privacy"})
        self.assertEqual(r["Location"], "/privacy/")
        self.assertIn("Past access", pat.get("/privacy/").content.decode())
        self.assertEqual(login(2001, "doc123").get("/privacy/").status_code, 302)  # doctors cannot open it

    def test_the_activity_tab_shows_views_and_emergency_reasons(self):
        s = self.s
        r1 = s.request_access(self.reyes, 1001); s.respond_to_request(r1.request_id, 1001, True)
        s.open_record(self.reyes, 1001)
        s.emergency_access(self.santos, 1001, "Collapsed in the lobby")
        page = login(1001, "pat123").get("/privacy/?tab=activity").content.decode()
        self.assertIn("Dr. Reyes", page)
        self.assertIn("Collapsed in the lobby", page)

    def test_patients_page_and_doctor_home(self):
        s = self.s
        doc = login(2001, "doc123")
        self.assertIn("No patient has approved you yet", doc.get("/patients/").content.decode())
        r1 = s.request_access(self.reyes, 1001); s.respond_to_request(r1.request_id, 1001, True)
        s.add_consultation(self.reyes, 1001, "Checkup")
        self.assertEqual(s.doctor_stats(2001), {"patients": 1, "pending": 0, "notes": 1, "emergencies": 0})
        self.assertIn("Juan Dela Cruz", doc.get("/patients/").content.decode())
        self.assertIn("Open record", doc.get("/dashboard/").content.decode())
        self.assertEqual(login(1001, "pat123").get("/patients/").status_code, 302)  # patients cannot open it

    def test_every_page_renders_without_leaks(self):
        doc, pat = login(2001, "doc123"), login(1001, "pat123")
        pages = [(doc, "/dashboard/"), (doc, "/patients/"), (doc, "/patients/?q=1001"), (doc, "/patients/?tab=waiting"),
                 (doc, "/patients/?tab=ended"), (doc, "/emergency/"), (doc, "/logout/"),
                 (pat, "/dashboard/"), (pat, "/record/"), (pat, "/privacy/"), (pat, "/privacy/?tab=activity"),
                 (pat, "/logout/"), (Client(), "/"), (Client(), "/register/")]
        for client, url in pages:
            r = client.get(url)
            body = r.content.decode()
            self.assertEqual(r.status_code, 200, url)
            self.assertNotIn("{%", body, url)
            self.assertNotIn("{{", body, url)
