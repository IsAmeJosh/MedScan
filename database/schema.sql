-- MedScan database schema. Safe to run again: every table is created only if it does not exist.
-- MedScan runs this file by itself on startup; you can also import it by hand in phpMyAdmin.
-- Passwords are plain text for now (hashing is a later step).

CREATE TABLE IF NOT EXISTS schema_version (
    version INT NOT NULL PRIMARY KEY
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS doctors (
    user_id      INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    password     VARCHAR(100) NOT NULL,
    specialty    VARCHAR(100) NOT NULL,
    clinic       VARCHAR(150) NOT NULL DEFAULT '',
    created_year SMALLINT NOT NULL
) ENGINE=InnoDB AUTO_INCREMENT=2001;

CREATE TABLE IF NOT EXISTS patients (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    password       VARCHAR(100) NOT NULL,
    sex            VARCHAR(20)  NOT NULL,
    date_of_birth  DATE NOT NULL,
    contact_number VARCHAR(11)  NOT NULL,                -- the mobile number: one per account, and a way to log in
    blood_type     VARCHAR(3)   NOT NULL DEFAULT '',
    created_year   SMALLINT NOT NULL,
    UNIQUE KEY uq_patient_mobile (contact_number),
    CONSTRAINT chk_patient_mobile CHECK (contact_number REGEXP '^09[0-9]{9}$'),
    CONSTRAINT chk_patient_blood  CHECK (blood_type IN ('', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'))
) ENGINE=InnoDB AUTO_INCREMENT=1001;

CREATE TABLE IF NOT EXISTS record_items (
    item_id    INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    kind       ENUM('allergy', 'surgery', 'medication') NOT NULL,
    item       VARCHAR(200) NOT NULL,
    INDEX idx_items_patient (patient_id),
    FOREIGN KEY (patient_id) REFERENCES patients (user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS consultations (
    consultation_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    doctor_id       INT NOT NULL,
    doctor_name     VARCHAR(100) NOT NULL,
    notes           TEXT NOT NULL,
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_consult_patient (patient_id),
    INDEX idx_consult_doctor (doctor_id),
    FOREIGN KEY (patient_id) REFERENCES patients (user_id),
    FOREIGN KEY (doctor_id)  REFERENCES doctors (user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS access_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT NOT NULL,
    patient_id INT NOT NULL,
    status     ENUM('Pending', 'Approved', 'Denied', 'Revoked') NOT NULL DEFAULT 'Pending',
    INDEX idx_requests_pair (patient_id, doctor_id),
    INDEX idx_requests_doctor (doctor_id, status),
    FOREIGN KEY (doctor_id)  REFERENCES doctors (user_id),
    FOREIGN KEY (patient_id) REFERENCES patients (user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS emergency_logs (
    log_id     INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT NOT NULL,
    patient_id INT NOT NULL,
    reason     VARCHAR(500) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_emergency_pair (doctor_id, patient_id, created_at),
    INDEX idx_emergency_patient (patient_id),
    FOREIGN KEY (doctor_id)  REFERENCES doctors (user_id),
    FOREIGN KEY (patient_id) REFERENCES patients (user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS record_views (
    view_id    INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id  INT NOT NULL,
    patient_id INT NOT NULL,
    via        ENUM('approved', 'emergency') NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_views_pair (patient_id, doctor_id),
    FOREIGN KEY (doctor_id)  REFERENCES doctors (user_id),
    FOREIGN KEY (patient_id) REFERENCES patients (user_id)
) ENGINE=InnoDB;

-- recipient_id is a patient OR a doctor, so the database cannot hold a foreign key for it
CREATE TABLE IF NOT EXISTS notifications (
    notification_id    INT AUTO_INCREMENT PRIMARY KEY,
    recipient_id       INT NOT NULL,
    message            VARCHAR(700) NOT NULL,
    related_request_id INT NULL,
    is_read            TINYINT(1) NOT NULL DEFAULT 0,
    created_at         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_notes_recipient (recipient_id, is_read)
) ENGINE=InnoDB;

INSERT IGNORE INTO schema_version (version) VALUES (4);
