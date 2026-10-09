"""Console demo. Run: python Main_Driver.py
Runs in memory only: no Django needed and nothing is saved."""
from logic.L_MedScan_System import MedScanSystem


def run_console_demo():
    """Walk through the core flow in memory: request, approve, note, emergency."""
    s = MedScanSystem()
    doc = s.register_doctor("Reyes", "doc123", "General Medicine")
    pat = s.register_patient("Juan Dela Cruz", "pat123", "Male", 30, "Penicillin", "Appendectomy")
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
    print("Allergies:", pat.record.allergies, "| Surgeries:", pat.record.surgeries)
    s.open_record(doc, pat.user_id)
    print("Record views logged:", len(s.view_rows_for_patient(pat.user_id)))
    print("Revoke access:", s.revoke_access(req.request_id, pat.user_id), "| now:", s.access_status(doc.user_id, pat.user_id))
    print("Note after revoke blocked:", s.add_consultation(doc, pat.user_id, "Too late") is None)
    s.emergency_access(doc, pat.user_id, "Unconscious patient")
    for n in s.inbox(pat.user_id):
        print("Notification:", n.message)


if __name__ == "__main__":
    run_console_demo()
