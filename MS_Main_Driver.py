"""MedScanSystem ties all classes together. Run this file for a console demo;
the Django website uses the same MedScanSystem object."""
import os
import pickle

from MS_Patient import Patient
from MS_Doctor import Doctor
from MS_Access_Request import AccessRequest
from MS_Emergency_Log import EmergencyLog
from MS_Notifications import Notification

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medscan_data.pkl")


class MedScanSystem:
    def __init__(self):
        self.patients = {}      # id -> Patient
        self.doctors = {}       # id -> Doctor
        self.requests = []
        self.emergency_logs = []
        self.notifications = []
        self._next_patient = 1001
        self._next_doctor = 2001

    # ---- persistence ----
    @staticmethod
    def load():
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "rb") as f:
                return pickle.load(f)
        system = MedScanSystem()
        system.register_doctor("Reyes", "doc123", "General Medicine")
        p = system.register_patient("Juan Dela Cruz", "pat123", "Male", 30, "Penicillin", "Appendectomy")
        system.save()
        return system

    def save(self):
        with open(DATA_FILE, "wb") as f:
            pickle.dump(self, f)

    # ---- registration / login ----
    def register_patient(self, name, password, sex, age, allergies="", surgeries=""):
        p = Patient(self._next_patient, name, password, sex, age)
        p.update_history(allergies, surgeries)
        self.patients[p.user_id] = p
        self._next_patient += 1
        return p

    def register_doctor(self, name, password, specialty):
        d = Doctor(self._next_doctor, name, password, specialty)
        self.doctors[d.user_id] = d
        self._next_doctor += 1
        return d

    def authenticate(self, user_id, password):
        user = self.patients.get(user_id) or self.doctors.get(user_id)
        return user if user and user.login(user_id, password) else None

    def get_user(self, user_id):
        return self.patients.get(user_id) or self.doctors.get(user_id)

    # ---- access control ----
    def request_access(self, doctor, patient_id):
        patient = self.patients.get(patient_id)
        if not patient:
            return None
        req = AccessRequest(len(self.requests) + 1, doctor.user_id, patient_id)
        self.requests.append(req)
        self._notify(patient_id, f"Dr. {doctor.name} requests access to your record.", req.request_id)
        return req

    def respond_to_request(self, request_id, approve):
        req = self.requests[request_id - 1]
        req.approve() if approve else req.deny()
        word = "approved" if approve else "denied"
        self._notify(req.doctor_id, f"Patient #{req.patient_id} {word} your access request.", req.request_id)

    def has_access(self, doctor_id, patient_id):
        return any(r.doctor_id == doctor_id and r.patient_id == patient_id and r.is_approved()
                for r in self.requests)

    def emergency_access(self, doctor, patient_id, reason):
        patient = self.patients.get(patient_id)
        if not patient:
            return None
        self.emergency_logs.append(EmergencyLog(len(self.emergency_logs) + 1, doctor.user_id, patient_id, reason))
        self._notify(patient_id, f"Dr. {doctor.name} opened your record in an emergency: {reason}")
        return patient

    def _notify(self, recipient_id, message, request_id=None):
        Notification(len(self.notifications) + 1, recipient_id, message, request_id).sendNotification(self.notifications)

    def inbox(self, user_id):
        return [n for n in reversed(self.notifications) if n.recipient_id == user_id]


if __name__ == "__main__":
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