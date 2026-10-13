"""Console demo. Run: python Main_Driver.py
Needs no website. It uses its own database, db_medscan_demo, which is rebuilt on every run,
so it never touches the data the website uses."""
from data.D_Database import Database
from logic.L_MedScan_System import MedScanSystem


def run_console_demo():
    """Walk through the core flow: request, approve, note, view, revoke, emergency."""
    db = Database.from_environment(name="db_medscan_demo")
    db.reset()  # fresh tables with the test accounts from database/seed.sql
    s = MedScanSystem(db)
    doc, pat = s.get_doctor(2001), s.get_patient(1001)
    assert doc is not None and pat is not None, "the test accounts from database/seed.sql are missing"
    print(doc, "|", pat)
    req = s.request_access(doc, pat.user_id)
    assert req is not None, "the first request should be accepted"
    print("Access before approval:", s.has_access(doc.user_id, pat.user_id))
    print("Duplicate request blocked:", s.request_access(doc, pat.user_id) is None)
    print("Note before approval blocked:", s.add_consultation(doc, pat.user_id, "Too early") is None)
    s.respond_to_request(req.request_id, pat.user_id, True)
    print("Access after approval:", s.has_access(doc.user_id, pat.user_id))
    note = s.add_consultation(doc, pat.user_id, "Mild fever, advised rest.")
    assert note is not None, "an approved doctor should be able to add a note"
    print(note.summary())
    second = s.add_consultation(doc, pat.user_id, "Follow-up in one week.")
    assert second is not None
    print("Consultation IDs:", note.consultation_id, second.consultation_id)
    pat = s.get_patient(pat.user_id)  # read again from the database
    assert pat is not None
    print("Allergies:", pat.record.allergies, "| Surgeries:", pat.record.surgeries, "| Age:", pat.age)
    s.open_record(doc, pat.user_id)
    print("Record views logged:", len(s.view_rows_for_patient(pat.user_id)))
    print("Revoke access:", s.revoke_access(req.request_id, pat.user_id), "| now:", s.access_status(doc.user_id, pat.user_id))
    print("Note after revoke blocked:", s.add_consultation(doc, pat.user_id, "Too late") is None)
    s.emergency_access(doc, pat.user_id, "Unconscious patient")
    print("Back in during the emergency hour:", s.can_view_record(doc.user_id, pat.user_id))
    for n in s.inbox(pat.user_id):
        print("Notification:", n.message)


if __name__ == "__main__":
    run_console_demo()
