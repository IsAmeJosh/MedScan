"""Console demo. Run: python Main_Driver.py
Runs in memory only: no Django needed and nothing is saved."""
from logic.L_MedScan_System import MedScanSystem


def run_console_demo():
    s = MedScanSystem()
    doc = s.register_doctor("Reyes", "doc123", "General Medicine")
    pat = s.register_patient("Juan Dela Cruz", "pat123", "Male", 30, "Penicillin", "Appendectomy")
    print(doc, "|", pat)
    req = s.request_access(doc, pat.user_id)
    print("Access before approval:", s.has_access(doc.user_id, pat.user_id))
    s.respond_to_request(req.request_id, True)
    print("Access after approval:", s.has_access(doc.user_id, pat.user_id))
    print(doc.add_consultation(pat, "Mild fever, advised rest.").summary())
    print("Allergies:", pat.record.allergies, "| Surgeries:", pat.record.surgeries)
    s.emergency_access(doc, pat.user_id, "Unconscious patient")
    for n in s.inbox(pat.user_id):
        print("Notification:", n.message)


if __name__ == "__main__":
    run_console_demo()
