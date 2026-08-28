CREATE TABLE IF NOT EXISTS pre_admissions (
    id BIGSERIAL PRIMARY KEY,
    pre_admission_code VARCHAR(50) NOT NULL UNIQUE,
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    appointment_id BIGINT REFERENCES appointments(id) ON DELETE SET NULL,
    expected_admission_date DATE NOT NULL,
    admission_type VARCHAR(50) NOT NULL CHECK (admission_type IN ('INPATIENT', 'DAYCARE', 'SURGERY')),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'DOCUMENTS_PENDING', 'READY', 'COMPLETED', 'CANCELLED')),
    pending_documents TEXT,
    submitted_documents TEXT,
    instructions TEXT,
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pre_admissions_patient_id ON pre_admissions(patient_id);
CREATE INDEX IF NOT EXISTS idx_pre_admissions_appointment_id ON pre_admissions(appointment_id);
CREATE INDEX IF NOT EXISTS idx_pre_admissions_code ON pre_admissions(pre_admission_code);
