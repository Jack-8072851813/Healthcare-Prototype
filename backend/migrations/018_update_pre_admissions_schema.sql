-- Migration 018: Update pre_admissions schema with doctor_id, department_id, checkin_time and expanded status lifecycle

ALTER TABLE pre_admissions
    ADD COLUMN IF NOT EXISTS doctor_id BIGINT REFERENCES doctors(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS department_id BIGINT REFERENCES departments(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS expected_checkin_time TIME WITHOUT TIME ZONE;

-- Drop existing status constraint if present and add updated constraint
ALTER TABLE pre_admissions DROP CONSTRAINT IF EXISTS pre_admissions_status_check;

ALTER TABLE pre_admissions
    ADD CONSTRAINT pre_admissions_status_check
    CHECK (status IN (
        'PENDING',
        'CONTACTED',
        'CONFIRMED',
        'DOCUMENTS_PENDING',
        'READY',
        'READY_FOR_ADMISSION',
        'ESCALATED',
        'COMPLETED',
        'CANCELLED'
    ));

-- Create indexes for fast filtering and reporting
CREATE INDEX IF NOT EXISTS idx_pre_admissions_patient_id ON pre_admissions(patient_id);
CREATE INDEX IF NOT EXISTS idx_pre_admissions_doctor_id ON pre_admissions(doctor_id);
CREATE INDEX IF NOT EXISTS idx_pre_admissions_department_id ON pre_admissions(department_id);
CREATE INDEX IF NOT EXISTS idx_pre_admissions_status ON pre_admissions(status);
CREATE INDEX IF NOT EXISTS idx_pre_admissions_expected_date ON pre_admissions(expected_admission_date);
