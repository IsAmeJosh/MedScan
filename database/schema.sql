-- MedScan database schema, version 3 (version 2 added a patient's height, weight and emergency contact; version 3 added the
-- health items: allergies, conditions, medications and vaccines, each with who added it and when).
-- MedScan runs this file by itself on startup. Every table is created only if it is missing, so it is safe to run again.
-- You can also import it by hand in phpMyAdmin.
--
-- Naming rules used in every table:
--   * tables start with tb_
--   * each table's primary key is <thing>_id (patient_id, request_id, ...)
--   * a link to another table repeats that table's key name (tb_consultations.patient_id -> tb_patients.patient_id)
--   * times end in _at, yes/no flags start with is_
--   * indexes start with ix_, unique keys with uq_, checks with ck_ and links with fk_
--
-- Patients get IDs from 1001 and doctors from 2001, so an ID alone tells the two apart.
-- Passwords are stored as plain text for now (hashing is a later step).

CREATE TABLE IF NOT EXISTS tb_schema_version (
    version INT NOT NULL PRIMARY KEY
) ENGINE=InnoDB;

-- ---------------------------------------------------------------- people

CREATE TABLE IF NOT EXISTS tb_doctors (
    doctor_id           INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    password            VARCHAR(100) NOT NULL,
    specialty           VARCHAR(100) NOT NULL,
    clinic              VARCHAR(150) NOT NULL DEFAULT '',
    mobile_number       VARCHAR(11)  NOT NULL DEFAULT '',   -- optional for doctors: '' means not given
    password_changed_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_year        SMALLINT     NOT NULL
) ENGINE=InnoDB AUTO_INCREMENT=2001;

CREATE TABLE IF NOT EXISTS tb_patients (
    patient_id          INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    password            VARCHAR(100) NOT NULL,
    sex                 VARCHAR(20)  NOT NULL,
    date_of_birth       DATE         NOT NULL,
    mobile_number       VARCHAR(11)  NOT NULL,              -- one per account, and a way to log in
    blood_type          VARCHAR(3)   NOT NULL DEFAULT '',   -- '' means not set
    password_changed_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_year        SMALLINT     NOT NULL,
    height_cm              SMALLINT      NULL,                -- optional: NULL means not added
    weight_kg              DECIMAL(4,1)  NULL,                -- optional: NULL means not added
    emergency_name         VARCHAR(100)  NOT NULL DEFAULT '', -- the emergency contact: '' means not added
    emergency_relationship VARCHAR(50)   NOT NULL DEFAULT '',
    emergency_mobile       VARCHAR(11)   NOT NULL DEFAULT '',
    UNIQUE KEY uq_patients_mobile (mobile_number),
    CONSTRAINT ck_patients_mobile CHECK (mobile_number REGEXP '^09[0-9]{9}$'),
    CONSTRAINT ck_patients_blood  CHECK (blood_type IN ('', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
    CONSTRAINT ck_patients_height CHECK (height_cm IS NULL OR height_cm BETWEEN 50 AND 250),
    CONSTRAINT ck_patients_weight CHECK (weight_kg IS NULL OR weight_kg BETWEEN 2 AND 300),
    CONSTRAINT ck_patients_emergency_mobile CHECK (emergency_mobile = '' OR emergency_mobile REGEXP '^09[0-9]{9}$')
) ENGINE=InnoDB AUTO_INCREMENT=1001;

-- ---------------------------------------------------------------- a patient's record

-- one row per allergy, surgery or medication
CREATE TABLE IF NOT EXISTS tb_medical_items (
    item_id    INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT          NOT NULL,
    item_type  ENUM('allergy', 'surgery', 'medication') NOT NULL,
    item_name  VARCHAR(200) NOT NULL,
    INDEX ix_medical_items_patient (patient_id),
    CONSTRAINT fk_medical_items_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- an allergy, a condition, a medication or a vaccine, with who added it and when
CREATE TABLE IF NOT EXISTS tb_health_items (
    item_id       INT AUTO_INCREMENT PRIMARY KEY,
    patient_id    INT          NOT NULL,
    kind          ENUM('allergy', 'condition', 'medication', 'vaccine') NOT NULL,
    name          VARCHAR(200) NOT NULL,                  -- the allergen, the condition, the medicine or the vaccine
    severity      ENUM('Mild', 'Moderate', 'Severe') NULL, -- allergies only
    reaction      VARCHAR(200) NOT NULL DEFAULT '',        -- allergies only: '' means not added
    status        ENUM('Active', 'Managed', 'Resolved') NULL, -- conditions only
    dose          VARCHAR(100) NOT NULL DEFAULT '',        -- medications only
    frequency     VARCHAR(100) NOT NULL DEFAULT '',        -- medications only: how often
    date_on       DATE         NULL,                       -- diagnosed (condition), started (medication) or given on (vaccine)
    added_by_role ENUM('patient', 'doctor') NOT NULL,
    added_by_id   INT          NOT NULL,
    added_by_name VARCHAR(100) NOT NULL,
    added_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_health_items_patient (patient_id, kind),
    CONSTRAINT fk_health_items_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- what a doctor added, changed or removed in a patient's health details (the patient sees it in Access, History)
CREATE TABLE IF NOT EXISTS tb_health_log (
    log_id     INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT          NOT NULL,
    doctor_id  INT          NOT NULL,
    action     ENUM('added', 'changed', 'removed') NOT NULL,
    kind       ENUM('allergy', 'condition', 'medication', 'vaccine') NOT NULL,
    item_name  VARCHAR(200) NOT NULL,
    created_at DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_health_log_patient (patient_id),
    CONSTRAINT fk_health_log_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id) ON DELETE CASCADE,
    CONSTRAINT fk_health_log_doctor  FOREIGN KEY (doctor_id)  REFERENCES tb_doctors (doctor_id)  ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tb_consultations (
    consultation_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT          NOT NULL,
    doctor_id       INT          NOT NULL,
    doctor_name     VARCHAR(100) NOT NULL,                 -- copied, so the note keeps the name the doctor had when writing it
    notes           TEXT         NOT NULL,
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_consultations_patient (patient_id),
    INDEX ix_consultations_doctor (doctor_id),
    CONSTRAINT fk_consultations_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id),
    CONSTRAINT fk_consultations_doctor  FOREIGN KEY (doctor_id)  REFERENCES tb_doctors (doctor_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------- access

CREATE TABLE IF NOT EXISTS tb_access_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT         NOT NULL,
    patient_id INT         NOT NULL,
    status     ENUM('Pending', 'Approved', 'Denied', 'Revoked') NOT NULL DEFAULT 'Pending',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),   -- when the doctor asked (or scanned)
    decided_at DATETIME(6) NULL,                                      -- when the status last left Pending
    via        ENUM('request', 'qr') NOT NULL DEFAULT 'request',      -- 'qr': approved by the patient's one-time QR code
    INDEX ix_access_requests_pair (patient_id, doctor_id),
    INDEX ix_access_requests_doctor (doctor_id, status),
    CONSTRAINT fk_access_requests_doctor  FOREIGN KEY (doctor_id)  REFERENCES tb_doctors (doctor_id),
    CONSTRAINT fk_access_requests_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id)
) ENGINE=InnoDB;

-- a patient's one-time QR code. Showing it to a doctor in person is the patient's approval, so it can be used once
-- and only for five minutes. spent_at is set when it is used, or when the patient asks for a new code.
CREATE TABLE IF NOT EXISTS tb_qr_tokens (
    token_id   INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT         NOT NULL,
    secret     CHAR(32)    NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    spent_at   DATETIME(6) NULL,
    UNIQUE KEY uq_qr_tokens_secret (secret),
    INDEX ix_qr_tokens_patient (patient_id, spent_at),
    CONSTRAINT fk_qr_tokens_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------- the audit trail (rows are only ever added)

CREATE TABLE IF NOT EXISTS tb_emergency_logs (
    log_id     INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT          NOT NULL,
    patient_id INT          NOT NULL,
    reason     VARCHAR(500) NOT NULL,
    created_at DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_emergency_logs_pair (doctor_id, patient_id, created_at),
    INDEX ix_emergency_logs_patient (patient_id),
    CONSTRAINT fk_emergency_logs_doctor  FOREIGN KEY (doctor_id)  REFERENCES tb_doctors (doctor_id),
    CONSTRAINT fk_emergency_logs_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tb_record_views (
    view_id    INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT         NOT NULL,
    patient_id INT         NOT NULL,
    via        ENUM('approved', 'emergency') NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_record_views_pair (patient_id, doctor_id),
    CONSTRAINT fk_record_views_doctor  FOREIGN KEY (doctor_id)  REFERENCES tb_doctors (doctor_id),
    CONSTRAINT fk_record_views_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id)
) ENGINE=InnoDB;

-- every time a doctor scanned a patient's code (shown in the patient's history)
CREATE TABLE IF NOT EXISTS tb_qr_scans (
    scan_id    INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT         NOT NULL,
    patient_id INT         NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_qr_scans_patient (patient_id),
    CONSTRAINT fk_qr_scans_doctor  FOREIGN KEY (doctor_id)  REFERENCES tb_doctors (doctor_id),
    CONSTRAINT fk_qr_scans_patient FOREIGN KEY (patient_id) REFERENCES tb_patients (patient_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------- notifications

-- recipient_id is a patient OR a doctor, so the database cannot hold a foreign key for it
CREATE TABLE IF NOT EXISTS tb_notifications (
    notification_id    INT AUTO_INCREMENT PRIMARY KEY,
    recipient_id       INT          NOT NULL,
    message            VARCHAR(700) NOT NULL,
    kind               ENUM('info', 'request', 'approved', 'denied', 'revoked', 'emergency', 'scan', 'note')
                       NOT NULL DEFAULT 'info',            -- what the message is about: decides where it leads
    related_request_id INT          NULL,
    is_read            TINYINT(1)   NOT NULL DEFAULT 0,
    created_at         DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX ix_notifications_recipient (recipient_id, is_read)
) ENGINE=InnoDB;

INSERT IGNORE INTO tb_schema_version (version) VALUES (3);
