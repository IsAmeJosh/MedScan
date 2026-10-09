"""Shared helpers for the tests."""
from data.D_Memory_Store import MemoryStore
from gui import G_Views
from logic.L_MedScan_System import MedScanSystem


def fresh_system():
    """A new system with the demo accounts (doctor 2001, patient 1001), used by the website too."""
    system = MedScanSystem.load(MemoryStore())
    G_Views.system = system
    return system


def build_sample_system():
    """A system with something in every table, for the store tests."""
    system = MedScanSystem.load(MemoryStore())
    reyes = system.doctors[2001]
    santos = system.register_doctor("Antonio Santos", "doc456", "Cardiology")
    juan = system.patients[1001]
    ana = system.register_patient("Ana Lopez", "ana123", "Female", 28, "Latex, Dust", "",
                                  contact_number="09281112222", medications="Cetirizine", blood_type="A+")
    approved = system.request_access(reyes, juan.user_id)
    system.respond_to_request(approved.request_id, juan.user_id, True)
    system.add_consultation(reyes, juan.user_id, "Headache for 3 days. Rest advised. Café intake reduced.")
    system.add_consultation(reyes, juan.user_id, "Follow-up: resolved.")
    system.open_record(reyes, juan.user_id)
    denied = system.request_access(santos, juan.user_id)
    system.respond_to_request(denied.request_id, juan.user_id, False)
    pending = system.request_access(santos, ana.user_id)
    system.emergency_access(santos, juan.user_id, "Patient unconscious on arrival")
    system.revoke_access(approved.request_id, juan.user_id)
    system.mark_inbox_read(juan.user_id)
    return system


def snapshot(system):
    """Everything about a system as plain data, so two systems can be compared."""
    people = [(p.user_id, p.name, p.sex, p.age, p.contact_number, p.display_id,
               p.record.blood_type, list(p.record.allergies), list(p.record.surgeries),
               list(p.record.medications),
               [(c.consultation_id, c.doctor_id, c.doctor_name, c.notes, c.date) for c in p.record.consultations])
              for p in system.patients.values()]
    doctors = [(d.user_id, d.name, d.specialty, d.display_id) for d in system.doctors.values()]
    return {
        "doctors": doctors,
        "patients": people,
        "requests": [(r.request_id, r.doctor_id, r.patient_id, r.status) for r in system.requests],
        "emergencies": [(e.log_id, e.doctor_id, e.patient_id, e.reason, e.timestamp) for e in system.emergency_logs],
        "views": [(v.view_id, v.doctor_id, v.patient_id, v.via, v.timestamp) for v in system.record_views],
        "notifications": [(n.notification_id, n.recipient_id, n.message, n.related_request_id, n.is_read, n.timestamp)
                          for n in system.notifications],
    }
