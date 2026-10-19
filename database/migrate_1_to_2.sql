-- Upgrade a version 1 database to version 2: a patient's height, weight and emergency contact.
-- MedScan runs this file by itself on startup when it finds a version 1 database (the data is kept).
-- Each statement is run once. A column that is already there is skipped, so running it again is harmless.

ALTER TABLE tb_patients ADD COLUMN height_cm SMALLINT NULL;
ALTER TABLE tb_patients ADD COLUMN weight_kg DECIMAL(4,1) NULL;
ALTER TABLE tb_patients ADD COLUMN emergency_name VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE tb_patients ADD COLUMN emergency_relationship VARCHAR(50) NOT NULL DEFAULT '';
ALTER TABLE tb_patients ADD COLUMN emergency_mobile VARCHAR(11) NOT NULL DEFAULT '';
ALTER TABLE tb_patients ADD CONSTRAINT ck_patients_height CHECK (height_cm IS NULL OR height_cm BETWEEN 50 AND 250);
ALTER TABLE tb_patients ADD CONSTRAINT ck_patients_weight CHECK (weight_kg IS NULL OR weight_kg BETWEEN 2 AND 300);
ALTER TABLE tb_patients ADD CONSTRAINT ck_patients_emergency_mobile CHECK (emergency_mobile = '' OR emergency_mobile REGEXP '^09[0-9]{9}$');

-- The data part: the demo patient (1001) gets the values from the design. Only while nothing is saved for them yet,
-- so a patient who already entered their own details keeps them.
UPDATE tb_patients
   SET height_cm = 170, weight_kg = 68, emergency_name = 'Maria Dela Cruz', emergency_relationship = 'Mother',
       emergency_mobile = '09187654321'
 WHERE patient_id = 1001 AND name = 'Juan Dela Cruz'
   AND height_cm IS NULL AND weight_kg IS NULL AND emergency_name = '';

UPDATE tb_schema_version SET version = 2;
