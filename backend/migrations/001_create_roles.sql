CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed default roles if they don't exist
INSERT INTO roles (name, description)
VALUES 
    ('ADMIN', 'Hospital Administrator with full access to patient records, dashboards, and system settings'),
    ('DOCTOR', 'Medical Doctor with access to assigned patient lists, appointments, schedules, and clinical notes')
ON CONFLICT (name) DO NOTHING;
