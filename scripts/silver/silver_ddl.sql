-- 1. Dimension Table: Currency Metadata
CREATE TABLE IF NOT EXISTS dim_currencies (
    currency_code VARCHAR(3) PRIMARY KEY,
    currency_name VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Seed basic currency metadata
INSERT INTO dim_currencies (currency_code, currency_name) VALUES
    ('EUR', 'Euro'),
    ('USD', 'United States Dollar'),
    ('PHP', 'Philippine Peso'),
    ('JPY', 'Japanese Yen'),
    ('GBP', 'British Pound Sterling'),
    ('CAD', 'Canadian Dollar'),
    ('AUD', 'Australian Dollar'),
    ('CHF', 'Swiss Franc'),
    ('CNY', 'Chinese Yuan')
ON CONFLICT (currency_code) DO NOTHING;


-- 2. Fact Table: Normalized Exchange Rates
CREATE TABLE IF NOT EXISTS silver_rates (
    rate_date DATE NOT NULL,
    base_currency VARCHAR(3) NOT NULL,
    target_currency VARCHAR(3) NOT NULL,
    exchange_rate NUMERIC(18, 6) NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite primary key guarantees idempotency
    PRIMARY KEY (rate_date, base_currency, target_currency),
    
    -- Foreign key checks
    CONSTRAINT fk_base_currency FOREIGN KEY (base_currency) REFERENCES dim_currencies (currency_code),
    CONSTRAINT fk_target_currency FOREIGN KEY (target_currency) REFERENCES dim_currencies (currency_code)
);

-- Indexes for performance on analytic queries
CREATE INDEX IF NOT EXISTS idx_silver_rates_date 
    ON silver_rates (rate_date DESC);

CREATE INDEX IF NOT EXISTS idx_silver_rates_pair 
    ON silver_rates (base_currency, target_currency, rate_date);