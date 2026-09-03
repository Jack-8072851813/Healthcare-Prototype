-- Migration 017: Add guardian/family member relationship fields to patients and create email_logs table.

ALTER TABLE patients ADD COLUMN IF NOT EXISTS guardian_patient_id BIGINT REFERENCES patients(id) ON DELETE SET NULL;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS guardian_phone VARCHAR(20);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS relationship_to_contact VARCHAR(50);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS is_dependent BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_patients_guardian_patient_id ON patients(guardian_patient_id);
CREATE INDEX IF NOT EXISTS idx_patients_relationship ON patients(relationship_to_contact);

-- Create email_logs table for tracking email deliverability and failure handling
CREATE TABLE IF NOT EXISTS email_logs (
    id BIGSERIAL PRIMARY KEY,
    email_type VARCHAR(50) NOT NULL,
    recipient VARCHAR(150) NOT NULL,
    appointment_id BIGINT REFERENCES appointments(id) ON DELETE SET NULL,
    doctor_id BIGINT REFERENCES doctors(id) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN (
        'EMAIL_PENDING', 'EMAIL_SENT', 'EMAIL_FAILED',
        'DOCTOR_WELCOME_EMAIL_PENDING', 'DOCTOR_WELCOME_EMAIL_SENT', 'DOCTOR_WELCOME_EMAIL_FAILED'
    )),
    provider_message_id VARCHAR(100),
    failure_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_email_logs_appointment_id ON email_logs(appointment_id);
CREATE INDEX IF NOT EXISTS idx_email_logs_doctor_id ON email_logs(doctor_id);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status);
