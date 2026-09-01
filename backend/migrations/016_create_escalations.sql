-- Migration 016: Create escalations table
-- Tracks human escalation cases when the AI cannot confidently resolve a patient request.

CREATE TABLE IF NOT EXISTS escalations (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    patient_id BIGINT REFERENCES patients(id) ON DELETE SET NULL,
    escalation_reason TEXT NOT NULL,
    patient_question TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED')),
    assigned_to_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    resolved_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_escalations_conv_id ON escalations(conversation_id);
CREATE INDEX IF NOT EXISTS idx_escalations_patient_id ON escalations(patient_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_escalations_created_at ON escalations(created_at);
