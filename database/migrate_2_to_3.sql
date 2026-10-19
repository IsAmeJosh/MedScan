-- Upgrade a version 2 database to version 3: allergies, conditions, medications and vaccines become health items that remember who added
-- them and when. MedScan runs this file by itself on startup when it finds a version 2 database (the data is kept).

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

-- The allergies and medications a patient already has move into the new table. Nobody wrote down who added them, so they count as
-- the patient's own. An allergy that had no severity before starts as Mild. Surgeries stay where they are.
INSERT INTO tb_health_items (patient_id, kind, name, severity, added_by_role, added_by_id, added_by_name)
SELECT m.patient_id, m.item_type, m.item_name, IF(m.item_type = 'allergy', 'Mild', NULL), 'patient', m.patient_id, p.name
  FROM tb_medical_items m JOIN tb_patients p ON p.patient_id = m.patient_id
 WHERE m.item_type IN ('allergy', 'medication')
 ORDER BY m.item_id;

DELETE FROM tb_medical_items WHERE item_type IN ('allergy', 'medication');

-- The demo patient's penicillin allergy gets the details from the design (only while it has none).
UPDATE tb_health_items
   SET severity = 'Severe', reaction = 'Hives, ER visit Jan 12, 2025'
 WHERE patient_id = 1001 AND kind = 'allergy' AND name = 'Penicillin' AND reaction = '';

UPDATE tb_schema_version SET version = 3;
