-- MedScan demo accounts. MedScan runs this file only when there are no doctors and no patients yet.
-- You can also import it by hand in phpMyAdmin after schema.sql.
--
--   Doctor   2001   password: doc123
--   Patient  1001   password: pat123

INSERT INTO tb_doctors (doctor_id, name, password, specialty, clinic, mobile_number, created_year) VALUES
    (2001, 'Reyes', 'doc123', 'General Medicine', 'Bayanihan Family Clinic', '09181112222', 2026);

INSERT INTO tb_patients (patient_id, name, password, sex, date_of_birth, mobile_number, blood_type, created_year,
                         height_cm, weight_kg, emergency_name, emergency_relationship, emergency_mobile) VALUES
    (1001, 'Juan Dela Cruz', 'pat123', 'Male', '1996-03-14', '09171234567', 'O+', 2026,
     170, 68, 'Maria Dela Cruz', 'Mother', '09187654321');

INSERT INTO tb_medical_items (patient_id, item_type, item_name) VALUES
    (1001, 'surgery', 'Appendectomy');

INSERT INTO tb_health_items (patient_id, kind, name, severity, reaction, added_by_role, added_by_id, added_by_name, added_at) VALUES
    (1001, 'allergy', 'Penicillin', 'Severe', 'Hives, ER visit Jan 12, 2025', 'patient', 1001, 'Juan Dela Cruz', '2026-10-01 09:00:00');
