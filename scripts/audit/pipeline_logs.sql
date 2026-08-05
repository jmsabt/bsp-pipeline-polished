-- =============================================================================
-- PIPELINE METADATA & AUDIT LOGS
-- Core operational table for pipeline observability and monitoring
-- =============================================================================

CREATE TABLE IF NOT EXISTS pipeline_logs (
    log_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,        -- e.g., 'silver_exchange_rates_load'
    run_type VARCHAR(20) NOT NULL,             -- 'BACKFILL' or 'DAILY'
    target_file VARCHAR(255),                  -- e.g., 'raw/2026/08/rates_2026-08-05.json'
    status VARCHAR(20) NOT NULL,               -- 'RUNNING', 'SUCCESS', 'FAILED'
    records_processed INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,
    duration_seconds NUMERIC(10, 2)
);

-- Index on pipeline execution history for quick UI/dashboard lookup
CREATE INDEX IF NOT EXISTS idx_pipeline_logs_status_date 
ON pipeline_logs (pipeline_name, started_at DESC);