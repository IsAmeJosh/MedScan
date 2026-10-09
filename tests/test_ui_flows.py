"""Walks through every page for both roles: login, search, requests, emergency, editing, registration."""
import re
import unittest
from datetime import datetime, timedelta

from django.test import Client

from gui import G_Views as V
from tests.helpers import fresh_system


class UIFlows(unittest.TestCase):
    def setUp(self):
        fresh_system()

    def test_every_page_and_flow(self):
        check = lambda label, cond: self.assertTrue(cond, label)
        html = lambda r: r.content.decode()
        s = V.system
        def html(r): return r.content.decode()

        # ---- logic
        check("parse_id plain", s.parse_id("1001") == 1001)
        check("parse_id PT format", s.parse_id("PT-2026-01001") == 1001)
        check("parse_id junk", s.parse_id("abc") is None and s.parse_id("") is None and s.parse_id(None) is None)
        juan = s.get_patient(1001)
        check("display ids", juan.display_id.startswith("PT-") and juan.display_id.endswith("-01001"))
        check("doctor display id", s.doctors[2001].display_id.startswith("DR-"))
        check("demo patient has contact + blood", juan.contact_number == "09171234567" and juan.record.blood_type == "O+")
        for bad in ["12345", "abcdefghij", "123456789012"]:
            try: s.update_patient_info(1001, "", "", "", "", bad); check(f"contact {bad} rejected", False)
            except ValueError: check(f"contact {bad} rejected", True)
        try: s.update_patient_info(1001, "", "", "", "Z+", ""); check("bad blood type rejected", False)
        except ValueError: check("bad blood type rejected", True)

        # ---- auth pages
        anon = Client()
        check("login page", anon.get("/").status_code == 200 and "auth-page" in html(anon.get("/")))
        check("register page", anon.get("/register/").status_code == 200)
        check("anon dashboard redirects", anon.get("/dashboard/").status_code == 302)
        check("anon search redirects", anon.get("/search/").status_code == 302)
        check("welcome without register redirects", anon.get("/welcome/").status_code == 302)

        # ---- doctor
        doc = Client()
        check("doctor logs in with PT-style? (DR format)", doc.post("/", {"user_id": s.doctors[2001].display_id, "password": "doc123"}).status_code == 302)
        pages = {"/dashboard/": "Recent requests", "/search/": "Search Patient", "/requests/": "Requests",
                 "/emergency/": "Emergency Access", "/logout/": "Log out of MedScan"}
        for url, text in pages.items():
            r = doc.get(url); check(f"doctor {url} 200 + content", r.status_code == 200 and text in html(r))
        r = doc.get("/dashboard/"); check("sidebar shows doctor identity", "Dr. Reyes" in html(r) and "DR-" in html(r) and "Search Patient" in html(r))
        check("doctor cannot open patient pages", doc.get("/record/").status_code == 302 and doc.get("/profile/").status_code == 302)
        r = doc.get("/search/?q=PT-2026-01001"); check("search by PT id shows locked", "Locked" in html(r) and "Send Access Request" in html(r))
        check("search by number works", "Juan Dela Cruz" in html(doc.get("/search/?q=1001")))
        check("search unknown id message", "No patient found" in html(doc.get("/search/?q=9999")))
        check("search junk no crash", doc.get("/search/?q=abc").status_code == 200)
        doc.post("/request/1001/")
        check("pending state shown", "Request pending" in html(doc.get("/search/?q=1001")) and "Send Access Request" not in html(doc.get("/search/?q=1001")))
        check("doctor requests list shows pending", "Pending" in html(doc.get("/requests/")))
        check("record locked before approval", doc.get("/patient/1001/").status_code == 302)

        # ---- patient
        pat = Client()
        check("patient logs in with number", pat.post("/", {"user_id": "1001", "password": "pat123"}).status_code == 302)
        for url, text in {"/dashboard/": "Access requests", "/record/": "Edit my information", "/profile/": "Doctors with access"}.items():
            r = pat.get(url); check(f"patient {url} 200 + content", r.status_code == 200 and text in html(r))
        r = pat.get("/dashboard/")
        check("patient sidebar + unread badge", "Patient" in html(r) and 'data-count="1"' in html(r) and "Dr. Reyes wants access" in html(r))
        check("notification panel lists the request", "requests access to your record" in html(r) and "unread" in html(r))
        check("patient cannot open doctor pages", pat.get("/search/").status_code == 302 and pat.get("/requests/").status_code == 302 and pat.get("/emergency/").status_code == 302)

        # notification read endpoint with CSRF enforced
        strict = Client(enforce_csrf_checks=True)
        login_token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html(strict.get("/"))).group(1)
        strict.post("/", {"user_id": "1001", "password": "pat123", "csrfmiddlewaretoken": login_token})
        check("read endpoint rejects missing CSRF", strict.post("/notifications/read/").status_code == 403)
        page = strict.get("/dashboard/")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html(page)).group(1)
        r = strict.post("/notifications/read/", HTTP_X_CSRFTOKEN=token)
        check("read endpoint works with CSRF header", r.status_code == 200 and s.unread_count(1001) == 0)
        check("badge hidden after read", "hidden" in html(strict.get("/dashboard/")).split('id="unread-badge"')[1][:80])
        check("anon cannot call read endpoint", anon.post("/notifications/read/").status_code in (403, 302) )

        # approve flow
        pat.post("/respond/1/approve/")
        check("approved shows in doctor search", "Access approved" in html(doc.get("/search/?q=1001")))
        check("doctor was notified with patient name", any("Juan Dela Cruz approved" in n.message for n in s.inbox(2001)))
        r = doc.get("/patient/1001/")
        check("record opens with all fields", r.status_code == 200 and "Allergies" in html(r) and "O+" in html(r) and "09171234567" in html(r) and "Penicillin" in html(r))
        doc.post("/patient/1001/consult/", {"notes": "Mild fever"})
        check("consult saved + visible", "Mild fever" in html(doc.get("/patient/1001/")) and "Mild fever" in html(pat.get("/record/")))

        # patient edit info
        r = pat.post("/record/edit/", {"allergies": "Peanuts, Latex", "surgeries": "", "medications": "Metformin", "blood_type": "A+", "contact_number": "0917 555 1234"}, follow=True)
        check("edit info saved", juan.record.allergies == ["Peanuts", "Latex"] and juan.record.medications == ["Metformin"] and juan.record.blood_type == "A+" and juan.contact_number == "09175551234")
        check("edit replaces, not appends", "Penicillin" not in juan.record.allergies and juan.record.surgeries == [])
        r = pat.post("/record/edit/", {"allergies": "x", "contact_number": "12"}, follow=True)
        check("bad contact shows error, no change", "10 to 11 digits" in html(r) and juan.record.allergies == ["Peanuts", "Latex"])

        # denied flow + request again
        s2 = s.register_patient("Maria Reyes", "m", "Female", 40)
        doc.post(f"/request/{s2.user_id}/")
        mar = Client(); mar.post("/", {"user_id": str(s2.user_id), "password": "m"})
        mar.post("/respond/2/deny/")
        r = doc.get(f"/search/?q={s2.user_id}")
        check("denied state + request again", "Access denied" in html(r) and "Request Again" in html(r))
        doc.post(f"/request/{s2.user_id}/")
        check("re-request after denial allowed", s.access_status(2001, s2.user_id) == "pending")

        # emergency via form
        r = doc.post("/emergency/", {"patient_id": "PT-2026-01001", "reason": ""})
        check("emergency needs reason", r.status_code == 200 and "reason is required" in html(r))
        r = doc.post("/emergency/", {"patient_id": "9999", "reason": "x"})
        check("emergency unknown patient", r.status_code == 200 and "No patient with that ID" in html(r))
        e = Client(); e.post("/", {"user_id": "2001", "password": "doc123"})
        p3 = s.register_patient("Eve", "e", "F", 22)
        check("emergency prefilled page", "Eve" in html(e.get(f"/patient/{p3.user_id}/emergency/")))
        r = e.post("/emergency/", {"patient_id": str(p3.user_id), "reason": "Collapsed"})
        check("emergency via form opens record", r.status_code == 302 and e.get(f"/patient/{p3.user_id}/").status_code == 200)
        check("emergency banner shown", "Emergency access" in html(e.get(f"/patient/{p3.user_id}/")))
        ev = Client(); ev.post("/", {"user_id": str(p3.user_id), "password": "e"})
        check("patient sees emergency log", "Collapsed" in html(ev.get("/dashboard/")))

        # register + welcome
        r = Client()
        check("bad contact on register -> form refilled", "10 to 11 digits" in html(r.post("/register/", {"role": "Patient", "name": "Zed", "password": "p", "age": "20", "contact_number": "12"})))
        r2 = r.post("/register/", {"role": "Patient", "name": "Zed", "password": "p", "age": "20", "contact_number": "0917 000 1111"}, follow=True)
        check("register -> welcome page shows PT id", r2.status_code == 200 and "PT-" in html(r2) and "all set" in html(r2))
        check("welcome id only shown once", r.get("/welcome/").status_code == 302)
        check("doctor register works", Client().post("/register/", {"role": "Doctor", "name": "Cruz", "password": "p", "specialty": "ENT"}).status_code == 302)
        check("logged-in user skips login page", pat.get("/").status_code == 302)

        # logout
        check("logout clears session", pat.post("/logout/").status_code == 302 and pat.get("/dashboard/").status_code == 302)

        # no leaked template syntax anywhere
        leak = [u for u in ["/dashboard/", "/search/?q=1001", "/requests/", "/patient/1001/"] if "{{" in html(doc.get(u)) or "{%" in html(doc.get(u))]
        check("no raw template tags in pages", not leak)


if __name__ == "__main__":
    unittest.main()
