-- Optional sample data, to make the screens look lived-in for a demo or a screen recording.
-- It is NOT loaded by default. Add it on top of the two demo accounts with:  python reset_database.py --demo
--
-- It adds three more doctors and four more patients (all with the password demo123), and a realistic mix of what can
-- happen between them: an approval by QR scan, an approval by request, a request still waiting, an emergency opening
-- and a denial. Everything is dated relative to now, so the screens always show "today", "yesterday" and so on.
--
-- Doctors:   Lim (Dermatology), Cruz (Emergency Medicine), Santos (Cardiology)
-- Patients:  Ana Ramos, Rosa Mendoza, Pedro Bautista, Luis Tan   (Juan Dela Cruz, 1001, already exists)

-- ---------------------------------------------------------------- people
INSERT INTO tb_doctors (name, password, specialty, clinic, mobile_number, created_year) VALUES
    ('Lim', 'demo123', 'Dermatology', 'Mabini Skin Center', '09182223333', 2026);
SET @lim = LAST_INSERT_ID();
INSERT INTO tb_doctors (name, password, specialty, clinic, mobile_number, created_year) VALUES
    ('Cruz', 'demo123', 'Emergency Medicine', 'Rizal Medical Center', '09183334444', 2026);
SET @cruz = LAST_INSERT_ID();
INSERT INTO tb_doctors (name, password, specialty, clinic, mobile_number, created_year) VALUES
    ('Santos', 'demo123', 'Cardiology', 'Northview Medical Center', '09184445555', 2026);
SET @santos = LAST_INSERT_ID();

INSERT INTO tb_patients (name, password, sex, date_of_birth, mobile_number, blood_type, created_year) VALUES
    ('Ana Ramos', 'demo123', 'Female', '1974-05-02', '09171110001', 'A+', 2026);
SET @ana = LAST_INSERT_ID();
INSERT INTO tb_patients (name, password, sex, date_of_birth, mobile_number, blood_type, created_year) VALUES
    ('Rosa Mendoza', 'demo123', 'Female', '1997-08-19', '09171110002', 'O-', 2026);
SET @rosa = LAST_INSERT_ID();
INSERT INTO tb_patients (name, password, sex, date_of_birth, mobile_number, blood_type, created_year) VALUES
    ('Pedro Bautista', 'demo123', 'Male', '1965-01-30', '09171110003', 'B+', 2026);
SET @pedro = LAST_INSERT_ID();
INSERT INTO tb_patients (name, password, sex, date_of_birth, mobile_number, blood_type, created_year) VALUES
    ('Luis Tan', 'demo123', 'Male', '2018-02-11', '09171110004', 'AB+', 2026);
SET @luis = LAST_INSERT_ID();

-- ---------------------------------------------------------------- a fuller record for Juan (1001)
INSERT INTO tb_health_items (patient_id, kind, name, severity, reaction, status, dose, frequency, date_on, added_by_role, added_by_id, added_by_name, added_at) VALUES
    (1001, 'allergy', 'Peanuts', 'Moderate', 'Swelling', NULL, '', '', NULL, 'patient', 1001, 'Juan Dela Cruz', NOW(6) - INTERVAL 20 DAY),
    (1001, 'condition', 'Hypertension', NULL, '', 'Managed', '', '', '2024-06-03', 'doctor', 2001, 'Reyes', NOW(6) - INTERVAL 8 DAY),
    (1001, 'medication', 'Amlodipine', NULL, '', NULL, '5 mg', 'once daily', '2024-06-10', 'doctor', 2001, 'Reyes', NOW(6) - INTERVAL 8 DAY),
    (1001, 'medication', 'Hydrocortisone', NULL, '', NULL, 'Cream', 'twice daily', CURDATE() - INTERVAL 3 DAY, 'doctor', @lim, 'Lim', NOW(6) - INTERVAL 3 DAY),
    (1001, 'vaccine', 'Flu shot', NULL, '', NULL, '', '', '2026-09-14', 'patient', 1001, 'Juan Dela Cruz', NOW(6) - INTERVAL 20 DAY),
    (1001, 'vaccine', 'COVID-19 booster', NULL, '', NULL, '', '', '2025-01-12', 'patient', 1001, 'Juan Dela Cruz', NOW(6) - INTERVAL 20 DAY),
    (1001, 'vaccine', 'Tetanus (Td)', NULL, '', NULL, '', '', '2021-05-20', 'patient', 1001, 'Juan Dela Cruz', NOW(6) - INTERVAL 20 DAY),
    (@ana, 'allergy', 'Latex', 'Moderate', 'Rash', NULL, '', '', NULL, 'patient', @ana, 'Ana Ramos', NOW(6) - INTERVAL 12 DAY),
    (@ana, 'medication', 'Metformin', NULL, '', NULL, '500 mg', 'with meals', NULL, 'patient', @ana, 'Ana Ramos', NOW(6) - INTERVAL 12 DAY),
    (@pedro, 'medication', 'Losartan', NULL, '', NULL, '50 mg', 'once daily', NULL, 'patient', @pedro, 'Pedro Bautista', NOW(6) - INTERVAL 12 DAY);

-- ---------------------------------------------------------------- Dr. Reyes (2001): the doctor's view
-- Juan: approved this morning by scanning his QR code, record opened, two notes written
INSERT INTO tb_access_requests (doctor_id, patient_id, status, created_at, decided_at, via) VALUES
    (2001, 1001, 'Approved', NOW(6) - INTERVAL 40 MINUTE, NOW(6) - INTERVAL 40 MINUTE, 'qr');
SET @reyes_juan = LAST_INSERT_ID();
INSERT INTO tb_qr_scans (doctor_id, patient_id, created_at) VALUES (2001, 1001, NOW(6) - INTERVAL 40 MINUTE);
INSERT INTO tb_record_views (doctor_id, patient_id, via, created_at) VALUES (2001, 1001, 'approved', NOW(6) - INTERVAL 35 MINUTE);
INSERT INTO tb_consultations (patient_id, doctor_id, doctor_name, notes, created_at) VALUES
    (1001, 2001, 'Reyes', 'Persistent headache for 3 days. BP 140/90. Advised rest, hydration and a follow-up in one week.', NOW(6) - INTERVAL 8 DAY),
    (1001, 2001, 'Reyes', 'Follow-up: BP 130/85, headache resolved. Continue Amlodipine 5 mg daily.', NOW(6) - INTERVAL 35 MINUTE);

-- Ana: approved by answering a request last week
INSERT INTO tb_access_requests (doctor_id, patient_id, status, created_at, decided_at, via) VALUES
    (2001, @ana, 'Approved', NOW(6) - INTERVAL 6 DAY, NOW(6) - INTERVAL 6 DAY + INTERVAL 20 MINUTE, 'request');
SET @reyes_ana = LAST_INSERT_ID();
INSERT INTO tb_record_views (doctor_id, patient_id, via, created_at) VALUES (2001, @ana, 'approved', NOW(6) - INTERVAL 5 DAY);

-- Pedro: a request that has not been answered yet
INSERT INTO tb_access_requests (doctor_id, patient_id, status, created_at) VALUES
    (2001, @pedro, 'Pending', NOW(6) - INTERVAL 3 HOUR);
SET @reyes_pedro = LAST_INSERT_ID();

-- Luis: an emergency opening, logged with its reason
INSERT INTO tb_emergency_logs (doctor_id, patient_id, reason, created_at) VALUES
    (2001, @luis, 'Child unconscious on arrival, parents not reachable', NOW(6) - INTERVAL 3 DAY);
INSERT INTO tb_record_views (doctor_id, patient_id, via, created_at) VALUES (2001, @luis, 'emergency', NOW(6) - INTERVAL 3 DAY);

-- Rosa: asked, and denied
INSERT INTO tb_access_requests (doctor_id, patient_id, status, created_at, decided_at, via) VALUES
    (2001, @rosa, 'Denied', NOW(6) - INTERVAL 5 DAY, NOW(6) - INTERVAL 5 DAY + INTERVAL 1 HOUR, 'request');
SET @reyes_rosa = LAST_INSERT_ID();

-- ---------------------------------------------------------------- Juan's other doctors: the patient's view
-- Dr. Lim: approved, record opened
INSERT INTO tb_access_requests (doctor_id, patient_id, status, created_at, decided_at, via) VALUES
    (@lim, 1001, 'Approved', NOW(6) - INTERVAL 2 DAY, NOW(6) - INTERVAL 2 DAY + INTERVAL 10 MINUTE, 'request');
INSERT INTO tb_record_views (doctor_id, patient_id, via, created_at) VALUES (@lim, 1001, 'approved', NOW(6) - INTERVAL 2 DAY + INTERVAL 15 MINUTE);

-- Dr. Cruz: used emergency access
INSERT INTO tb_emergency_logs (doctor_id, patient_id, reason, created_at) VALUES
    (@cruz, 1001, 'Unconscious on arrival, ER', NOW(6) - INTERVAL 3 DAY);
INSERT INTO tb_record_views (doctor_id, patient_id, via, created_at) VALUES (@cruz, 1001, 'emergency', NOW(6) - INTERVAL 3 DAY);

-- Dr. Santos: waiting for Juan's answer
INSERT INTO tb_access_requests (doctor_id, patient_id, status, created_at) VALUES
    (@santos, 1001, 'Pending', NOW(6) - INTERVAL 2 HOUR);
SET @santos_juan = LAST_INSERT_ID();

-- ---------------------------------------------------------------- the bell
INSERT INTO tb_notifications (recipient_id, message, kind, related_request_id, is_read, created_at) VALUES
    (1001, 'Dr. Santos requests access to your record.', 'request', @santos_juan, 0, NOW(6) - INTERVAL 2 HOUR),
    (1001, 'Dr. Reyes scanned your QR code and can now open your record.', 'scan', @reyes_juan, 0, NOW(6) - INTERVAL 40 MINUTE),
    (1001, 'Dr. Cruz opened your record in an emergency: Unconscious on arrival, ER', 'emergency', NULL, 1, NOW(6) - INTERVAL 3 DAY),
    (2001, 'Ana Ramos approved your access request.', 'approved', @reyes_ana, 1, NOW(6) - INTERVAL 6 DAY),
    (2001, 'Rosa Mendoza denied your access request.', 'denied', @reyes_rosa, 1, NOW(6) - INTERVAL 5 DAY);
