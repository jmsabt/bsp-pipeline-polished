# Automated BSP Exchange Rates Medallion Pipeline

Welcome to the **Automated BSP Exchange Rates Medallion Pipeline** repository! 🚀

This project demonstrates an end-to-end, automated data engineering pipeline using a **Medallion Architecture** to ingest, clean, store, and expose financial exchange rate data. Built as a portfolio-ready data pipeline, it showcases production practices in pipeline orchestration, operational control logging, data modeling, and CI/CD automation.

---

## 🏗️ Data Architecture

The architecture follows the classic Medallion Architecture across **Bronze**, **Silver**, and **Gold** layers:

```
[ Frankfurter API ]
        │
        ▼ (Extraction & Raw JSON Storage)
┌────────────────────────────────────────────────────────┐
│ BRONZE LAYER: Supabase Storage Bucket                  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (Flattening, Normalization & Upserts)
┌────────────────────────────────────────────────────────┐
│ SILVER LAYER: Supabase PostgreSQL                      │
│ - Primary Key & Foreign Key Constraints                │
│ - Idempotent ON CONFLICT Logic                         │
│ - Operational Control Plane (`pipeline_logs`)          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (Business Reporting & Dynamic Aggregations)
┌────────────────────────────────────────────────────────┐
│ GOLD LAYER: Analytical Views                           │
│ - `gold_daily_rate_changes`                            │
│ - `gold_monthly_currency_summary`                      │
│ - `gold_cross_rates_php`                               │
└────────────────────────────────────────────────────────┘

```

1. **Bronze Layer**: Raw exchange rate JSON payloads extracted from the Frankfurter REST API and archived as immutable objects in Supabase Storage.
2. **Silver Layer**: Data transformation pipeline that parses, normalizes, and deduplicates raw records into relational PostgreSQL tables (`silver_rates` and `dim_currencies`) using idempotent `ON CONFLICT` upserts.
3. **Gold Layer**: Business-ready analytical views designed for reporting and consumption by downstream BI tools like Power BI.

---

## 📖 Project Overview

This project features:

1. **Medallion Data Architecture**: Structuring chaotic raw API payloads into a clean, queryable PostgreSQL warehouse.
2. **Automated Backfill & ETL**: Processing 260,000+ historical exchange rate records with automated currency dimension seeding.
3. **Operational Observability (Control Plane)**: A custom `pipeline_logs` tracking table logging execution metrics, status, rows processed, duration, and error tracebacks.
4. **CI/CD Pipeline Automation**: Fully scheduled daily execution via GitHub Actions with secure secrets management.

🎯 This repository showcases practical expertise in:

- Python Data Pipelines & APIs (`requests`, `psycopg2`, `supabase-py`)
- Data Engineering & Medallion Architecture
- PostgreSQL Database Administration & Query Optimization
- CI/CD Automation (GitHub Actions)
- Observability & Operational Auditing

---

## 🛠️ Tools & Technologies

- **Python 3.10+**: Core programming language for extraction, transformation, and database loading.
- **Supabase Storage**: Object storage housing raw JSON files (Bronze Layer).
- **Supabase PostgreSQL**: Managed database hosting relational tables and analytic views (Silver & Gold Layers).
- **GitHub Actions**: Automated runner for daily batch execution at 00:00 UTC.
- **Power BI (Optional)**: Business intelligence tool connected via DirectQuery/Import for financial visualization.

---

## 🚀 Project Requirements & Specifications

### 1. Data Ingestion & Storage (Bronze Layer)

- Ingest historical and daily exchange rates from the Frankfurter REST API.
- Save immutable raw JSON payloads directly to Supabase Cloud Storage.

### 2. Transformation & Quality (Silver Layer)

- Unnest nested JSON key-value pairs into structured rows.
- Ensure pipeline idempotency via `ON CONFLICT (rate_date, currency_code) DO UPDATE` queries.
- Populate relational dimensions (`dim_currencies`) and maintain foreign key integrity.

### 3. Analytics & Reporting (Gold Layer)

- Generate dynamic SQL views calculating rolling moving averages, month-over-month summaries, and PHP cross-rates.

### 4. Pipeline Observability

- Record execution logs to `pipeline_logs` for every pipeline execution to track row counts, execution duration, and failure traces.

---

## 📂 Repository Structure

```
bsp-pipeline-polished/
│
├── .github/
│   └── workflows/
│       └── daily_ingestion.yml     # GitHub Actions workflow for scheduled pipeline execution
│
├── docs/                           # Documentation, schema design, and preview screenshots
│
├── scripts/                        # Pipeline execution scripts split by Medallion layer
│   ├── bronze/                     # API extraction and object storage scripts
│   ├── silver/                     # Data cleaning, normalization, and PostgreSQL load scripts
│   └── gold/                       # SQL DDL scripts creating dynamic analytical views
│
├── tests/                          # Pipeline assertions and SQL log verification queries
│
├── .gitignore                      # Environment variables and cache exclusion rules
├── LICENSE                         # License details
├── README.md                       # Project overview and system architecture details
└── requirements.txt                # Python dependencies

```

---
