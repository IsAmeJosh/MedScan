-- MedScan demo accounts. MedScan runs this file only when there are no doctors and no patients yet.
-- You can also import it by hand in phpMyAdmin after schema.sql.
--
--   Doctor   2001   password: doc123
--   Patient  1001   password: pat123

INSERT INTO tb_doctors (doctor_id, name, password, specialty, clinic, mobile_number, created_year) VALUES
    (2001, 'Reyes', 'doc123', 'General Medicine', 'Bayanihan Family Clinic', '09181112222', 2026);

INSERT INTO tb_patients (patient_id, name, password, sex, date_of_birth, mobile_number, blood_type, created_year) VALUES
    (1001, 'Juan Dela Cruz', 'pat123', 'Male', '1996-03-14', '09171234567', 'O+', 2026);

INSERT INTO tb_medical_items (patient_id, item_type, item_name) VALUES
    (1001, 'allergy', 'Penicillin'),
    (1001, 'surgery', 'Appendectomy');
