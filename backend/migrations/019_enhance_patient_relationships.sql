-- Migration 019: Enhance patient relationship indexing and lookup performance

CREATE INDEX IF NOT EXISTS idx_patients_guardian_patient_status ON patients(guardian_patient_id, status);
CREATE INDEX IF NOT EXISTS idx_patients_guardian_phone_status ON patients(guardian_phone, status);
CREATE INDEX IF NOT EXISTS idx_patients_is_dependent_status ON patients(is_dependent, status);
