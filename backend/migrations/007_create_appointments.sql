CREATE TABLE IF NOT EXISTS appointments (
    id BIGSERIAL PRIMARY KEY,
    booking_id VARCHAR(50) NOT NULL UNIQUE,
    patient_id BIGINT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    doctor_id BIGINT NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    department_id BIGINT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('BOOKED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'RESCHEDULED', 'NO_SHOW')),
    booking_source VARCHAR(20) NOT NULL CHECK (booking_source IN ('WHATSAPP_TEXT', 'WHATSAPP_VOICE', 'ADMIN', 'DOCTOR')),
    patient_reason TEXT,
    cancellation_reason TEXT,
    reschedule_reason TEXT,
    cancelled_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    rescheduled_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    rescheduled_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_appointments_booking_id ON appointments(booking_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);

-- Critical double-booking prevention constraint using a partial unique index.
-- It ensures that a doctor cannot have more than one active appointment (not CANCELLED or RESCHEDULED) at a given date/time slot.
CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_double_booking
ON appointments(doctor_id, appointment_date, appointment_time)
WHERE status NOT IN ('CANCELLED', 'RESCHEDULED');
