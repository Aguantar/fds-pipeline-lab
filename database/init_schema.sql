-- ============================================
-- FDS 프로젝트 전용 스키마 생성
-- ============================================

CREATE SCHEMA IF NOT EXISTS fds;

-- ============================================
-- Part A: 트랜잭션 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS fds.transactions (
    id SERIAL PRIMARY KEY,
    tx_id VARCHAR(50) UNIQUE NOT NULL,
    card_number VARCHAR(20) NOT NULL,
    amount BIGINT NOT NULL,
    merchant VARCHAR(100),
    is_fraud BOOLEAN DEFAULT false,
    fraud_rules TEXT[],
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fds_transactions_created_at 
ON fds.transactions(created_at);

CREATE INDEX IF NOT EXISTS idx_fds_transactions_card_number 
ON fds.transactions(card_number);

CREATE INDEX IF NOT EXISTS idx_fds_transactions_is_fraud 
ON fds.transactions(is_fraud) WHERE is_fraud = true;

-- ============================================
-- Part A: 일별 집계 테이블
-- ============================================

CREATE TABLE IF NOT EXISTS fds.daily_transaction_summary (
    id SERIAL PRIMARY KEY,
    summary_date DATE NOT NULL,
    total_count BIGINT,
    total_amount BIGINT,
    fraud_count BIGINT,
    fraud_amount BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(summary_date)
);

-- ============================================
-- Part B: 파이프라인 완료 기록
-- ============================================

CREATE TABLE IF NOT EXISTS fds.pipeline_completion_log (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    execution_time TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    records_processed INT,
    status VARCHAR(20),
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_fds_pipeline_completion_name_time 
ON fds.pipeline_completion_log(pipeline_name, execution_time);

-- ============================================
-- Part B: SLA 정의
-- ============================================

CREATE TABLE IF NOT EXISTS fds.sla_definitions (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    sla_type VARCHAR(20) NOT NULL,
    deadline_minutes INT,
    owner VARCHAR(50),
    slack_channel VARCHAR(50),
    enabled BOOLEAN DEFAULT true
);

-- ============================================
-- Part B: SLA 위반 이력
-- ============================================

CREATE TABLE IF NOT EXISTS fds.sla_violations (
    id SERIAL PRIMARY KEY,
    sla_id INT REFERENCES fds.sla_definitions(id),
    pipeline_name VARCHAR(100),
    expected_by TIMESTAMP,
    detected_at TIMESTAMP,
    violation_minutes INT,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_fds_sla_violations_detected 
ON fds.sla_violations(detected_at);

-- ============================================
-- 초기 SLA 데이터
-- ============================================

INSERT INTO fds.sla_definitions (pipeline_name, sla_type, deadline_minutes, owner, slack_channel) 
VALUES
    ('consumer_batch', 'hourly', 5, 'data-team', '#data-alerts'),
    ('daily_aggregation', 'daily', 540, 'data-team', '#data-alerts')
ON CONFLICT DO NOTHING;
