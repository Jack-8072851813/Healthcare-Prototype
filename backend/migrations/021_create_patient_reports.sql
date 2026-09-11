-- Migration 021: Create patient_reports table for medical reports feature
CREATE TABLE IF NOT EXISTS patient_reports (
    id SERIAL PRIMARY KEY,
    report_reference VARCHAR(64) UNIQUE NOT NULL,
    patient_id INT REFERENCES patients(id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL,
    report_title VARCHAR(255) NOT NULL,
    report_date DATE NOT NULL,
    doctor_id INT REFERENCES doctors(id) ON DELETE SET NULL,
    department_id INT REFERENCES departments(id) ON DELETE SET NULL,
    status VARCHAR(30) DEFAULT 'Available',
    summary TEXT NOT NULL,
    file_reference VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_reports_patient_id ON patient_reports(patient_id);
