-- RAG System Database Initialization
-- PostgreSQL 15 with pg_vector extension
-- Ollama専用版

-- pg_vector拡張機能を有効化
CREATE EXTENSION IF NOT EXISTS vector;

-- ドキュメント情報を保存するテーブル
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    file_type VARCHAR(50),
    upload_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'uploaded',
    metadata JSONB,
    content_preview TEXT,
    total_chunks INTEGER DEFAULT 0
);

-- ドキュメントチャンク（分割されたテキスト）を保存するテーブル
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768), -- nomic-embed-textの次元数（GPT-OSS最適化）
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_document_chunk UNIQUE (document_id, chunk_index)
);

-- 会話履歴を保存するテーブル
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source_chunks JSONB,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- インデックスの作成
-- ベクトル検索用のインデックス（HNSW法）
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- 文書検索用のインデックス
CREATE INDEX IF NOT EXISTS idx_documents_filename 
ON documents(filename);

CREATE INDEX IF NOT EXISTS idx_documents_upload_time 
ON documents(upload_time);

CREATE INDEX IF NOT EXISTS idx_documents_status 
ON documents(status);

-- チャンク検索用のインデックス
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id 
ON document_chunks(document_id);

-- 会話履歴検索用のインデックス
CREATE INDEX IF NOT EXISTS idx_conversations_session_id 
ON conversations(session_id);

CREATE INDEX IF NOT EXISTS idx_conversations_created_at 
ON conversations(created_at);

-- 全文検索用のインデックス（多言語対応）
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_gin 
ON document_chunks USING gin(to_tsvector('english', content));

-- 関数: ベクトル類似度検索
CREATE OR REPLACE FUNCTION search_similar_chunks(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.7,
    max_results integer DEFAULT 10
)
RETURNS TABLE (
    chunk_id integer,
    document_id integer,
    filename varchar,
    content text,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dc.id as chunk_id,
        dc.document_id,
        d.filename,
        dc.content,
        1 - (dc.embedding <=> query_embedding) as similarity
    FROM document_chunks dc
    JOIN documents d ON dc.document_id = d.id
    WHERE 1 - (dc.embedding <=> query_embedding) > similarity_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- 統計情報表示用のビュー
CREATE OR REPLACE VIEW document_stats AS
SELECT 
    COUNT(*) as total_documents,
    COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_documents,
    COUNT(CASE WHEN status = 'uploaded' THEN 1 END) as pending_documents,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as error_documents,
    SUM(file_size) as total_file_size,
    SUM(total_chunks) as total_chunks
FROM documents;

-- 初期化完了のログ
INSERT INTO conversations (session_id, question, answer, metadata) 
VALUES (
    'system', 
    'Database initialized', 
    'RAG system database has been successfully initialized with pg_vector extension.',
    '{"version": "2.0", "locale": "C.UTF-8", "supports": ["ollama"]}'::jsonb
)
ON CONFLICT DO NOTHING;

-- 権限設定
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO raguser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO raguser;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO raguser;
