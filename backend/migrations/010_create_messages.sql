CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_type VARCHAR(20) NOT NULL CHECK (sender_type IN ('PATIENT', 'AI_AGENT', 'SYSTEM', 'ADMIN', 'DOCTOR')),
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('TEXT', 'VOICE', 'SYSTEM')),
    message_text TEXT,
    language VARCHAR(20) CHECK (language IN ('ENGLISH', 'TAMIL', 'HINDI', 'TELUGU', 'MALAYALAM', 'KANNADA', 'URDU')),
    intent VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_intent ON messages(intent);
