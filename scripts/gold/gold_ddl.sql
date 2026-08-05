-- =============================================================================
-- GOLD LAYER ANALYTIC VIEWS
-- Pipeline: Frankfurter API -> Supabase Storage (Bronze) -> Postgres (Silver/Gold)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Daily Rate Changes & Moving Averages
-- Calculates day-over-day changes, percentage shift, and a 7-day moving average.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold_daily_rate_changes AS
WITH daily_lag AS (
    SELECT 
        rate_date,
        base_currency,
        target_currency,
        exchange_rate,
        LAG(exchange_rate) OVER (
            PARTITION BY base_currency, target_currency 
            ORDER BY rate_date
        ) AS prior_day_rate,
        AVG(exchange_rate) OVER (
            PARTITION BY base_currency, target_currency 
            ORDER BY rate_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg
    FROM silver_rates
)
SELECT 
    rate_date,
    base_currency,
    target_currency,
    exchange_rate,
    prior_day_rate,
    ROUND((exchange_rate - prior_day_rate)::numeric, 4) AS daily_change,
    ROUND(
        CASE 
            WHEN prior_day_rate IS NOT NULL AND prior_day_rate != 0 
            THEN ((exchange_rate - prior_day_rate) / prior_day_rate * 100)::numeric
            ELSE 0 
        END, 4
    ) AS pct_daily_change,
    ROUND(rolling_7d_avg::numeric, 4) AS rolling_7d_avg
FROM daily_lag;


-- -----------------------------------------------------------------------------
-- 2. Monthly Currency Summary
-- Aggregates daily rate data into monthly high, low, average, and trading days.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold_monthly_currency_summary AS
SELECT 
    DATE_TRUNC('month', rate_date)::DATE AS month_start,
    base_currency,
    target_currency,
    ROUND(AVG(exchange_rate)::numeric, 4) AS avg_exchange_rate,
    MIN(exchange_rate) AS min_exchange_rate,
    MAX(exchange_rate) AS max_exchange_rate,
    COUNT(*) AS trading_days_count
FROM silver_rates
GROUP BY 1, 2, 3;


-- -----------------------------------------------------------------------------
-- 3. Cross Rates Relative to PHP (Philippine Peso)
-- Derives direct exchange rates against PHP (e.g., USD/PHP, JPY/PHP) from EUR rates.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold_cross_rates_php AS
WITH php_rates AS (
    SELECT 
        rate_date, 
        exchange_rate AS eur_to_php
    FROM silver_rates
    WHERE target_currency = 'PHP'
)
SELECT 
    s.rate_date,
    s.target_currency AS currency_code,
    s.exchange_rate AS rate_in_eur,
    p.eur_to_php,
    ROUND((p.eur_to_php / s.exchange_rate)::numeric, 4) AS rate_in_php
FROM silver_rates s
JOIN php_rates p ON s.rate_date = p.rate_date
WHERE s.target_currency != 'PHP';