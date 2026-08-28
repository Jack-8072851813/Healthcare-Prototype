-- Enable vector extension for pgvector support
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_number INTEGER NOT NULL CHECK (chunk_number > 0),
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK (token_count >= 0),
    metadata JSONB,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc_id ON knowledge_chunks(document_id);
-- Approximate Nearest Neighbor (ANN) index can be added if required, but standard index is enough for the POC.
