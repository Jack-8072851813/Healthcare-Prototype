CREATE TABLE IF NOT EXISTS agent_action_logs (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    patient_id BIGINT REFERENCES patients(id) ON DELETE SET NULL,
    action_name VARCHAR(50) NOT NULL CHECK (action_name IN ('SEARCH_HOSPITAL_KNOWLEDGE', 'GET_DOCTOR_AVAILABILITY', 'GET_AVAILABLE_SLOTS', 'BOOK_APPOINTMENT', 'GET_APPOINTMENT_STATUS', 'CANCEL_APPOINTMENT', 'RESCHEDULE_APPOINTMENT', 'GET_PATIENT', 'GET_PRE_ADMISSION_STATUS', 'CREATE_ESCALATION')),
    intent VARCHAR(50),
    input_data JSONB,
    output_data JSONB,
    status VARCHAR(20) NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'REJECTED')),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_action_logs_conv_id ON agent_action_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_action_logs_pat_id ON agent_action_logs(patient_id);
