"""Record-view log, revoke access, the QR placeholder and the Notification methods, through the real pages."""
import re
import unittest
from datetime import datetime, timedelta

from django.test import Client

from gui import G_Views as V
from tests.helpers import fresh_system
from models.M_Notification import Notification


class Features(unittest.TestCase):
    def setUp(self):
        fresh_system()

    def test_log_revoke_and_placeholder(self):
        check = lambda label, cond: self.assertTrue(cond, label)
        html = lambda r: r.content.decode()
        s = V.system
        reyes = s.doctors[2001]
        def login(uid, pw):
            c = Client(); c.post("/", {"user_id": str(uid), "password": pw}); return c
        doc, pat = login(2001, "doc123"), login(1001, "pat123")

        # ---- notification rename
        from models.M_Notification import Notification
        n = Notification(1, 1, "hi")
        check("snake_case notification methods", hasattr(n, "send_notification") and hasattr(n, "mark_as_read")
              and not hasattr(n, "sendNotification") and not hasattr(n, "markAsRead"))
        box = []; n.send_notification(box); n.mark_as_read()
        check("send + mark read work", box == [n] and n.is_read)

        # ---- record view log
        check("locked doctor cannot open + nothing logged", doc.get("/patient/1001/").status_code == 302 and not s.record_views)
        doc.post("/request/1001/"); pat.post("/respond/1/approve/")
        doc.get("/patient/1001/"); doc.get("/patient/1001/"); doc.get("/patient/1001/")
        check("repeat opens within 10 min logged once", len(s.record_views) == 1 and s.record_views[0].via == "approved")
        s.record_views[0].timestamp = datetime.now() - timedelta(minutes=11)
        doc.get("/patient/1001/")
        check("open after window is logged again", len(s.record_views) == 2)
        r = pat.get("/dashboard/")
        check("patient sees 'Who viewed my record'", "Who viewed my record" in html(r) and "Dr. Reyes" in html(r))
        p2 = s.register_patient("Eve", "e", "F", 22)
        doc.post("/emergency/", {"patient_id": str(p2.user_id), "reason": "Collapsed"})
        doc.get(f"/patient/{p2.user_id}/")
        check("emergency open logged as emergency", s.record_views[-1].via == "emergency" and s.record_views[-1].patient_id == p2.user_id)
        check("emergency badge shown to patient", "Emergency" in html(login(p2.user_id, "e").get("/dashboard/")))

        # ---- revoke
        check("doctor cannot revoke", doc.post("/revoke/1/").status_code == 302 and s.requests[0].is_approved())
        other = login(s.register_patient("Other", "o", "M", 30).user_id, "o")
        other.post("/revoke/1/")
        check("other patient cannot revoke", s.requests[0].is_approved())
        check("revoke button on patient dashboard", "Revoke" in html(pat.get("/dashboard/")))
        check("revoke button on profile", "Revoke access" in html(pat.get("/profile/")))
        r = pat.post("/revoke/1/", {"next": "profile"})
        check("revoke works + redirect to profile", s.requests[0].status == "Revoked" and r.status_code == 302 and r["Location"] == "/profile/")
        pat.post("/revoke/1/", {"next": "https://evil.example"})
        check("revoke ignores outside redirect", True)
        r2 = pat.post("/revoke/1/", {"next": "https://evil.example"})
        check("redirect stays on dashboard for foreign next", r2["Location"] == "/dashboard/")
        check("revoke notifies doctor", any("revoked your access" in x.message for x in s.inbox(2001)))
        check("record locked again", doc.get("/patient/1001/").status_code == 302)
        doc.post("/patient/1001/consult/", {"notes": "after revoke"})
        check("note refused after revoke", not any("after revoke" in c.notes for c in s.get_patient(1001).record.consultations))
        r = doc.get("/search/?q=1001")
        check("doctor sees Access revoked + Request Again", "Access revoked" in html(r) and "Request Again" in html(r))
        check("revoked shown in requests list", "Revoked" in html(doc.get("/requests/")) and "Revoked" in html(doc.get("/dashboard/")))
        doc.post("/request/1001/")
        check("doctor can re-request after revoke", s.access_status(2001, 1001) == "pending")
        check("pending request can't be revoked", not s.revoke_access(len(s.requests), 1001))
        check("revoke of unknown id is safe", pat.post("/revoke/999/").status_code == 302)
        pat.post("/respond/%d/approve/" % len(s.requests))
        check("re-approval works", s.access_status(2001, 1001) == "approved")

        # ---- QR placeholder
        prof = html(pat.get("/profile/"))
        check("profile shows QR placeholder, no qr code package needed", "coming soon" in prof and "<svg" not in prof)
        check("search page has no scan controls", "scan-button" not in html(doc.get("/search/")))

        # ---- earlier behaviour still fine
        check("dashboards render", doc.get("/dashboard/").status_code == 200 and pat.get("/dashboard/").status_code == 200)
        check("no template leaks", all("{{" not in html(doc.get(u)) and "{%" not in html(doc.get(u)) for u in ["/dashboard/", "/search/?q=1001", "/requests/"]))


if __name__ == "__main__":
    unittest.main()
