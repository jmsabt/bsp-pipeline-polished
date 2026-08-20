# Automated BSP Exchange Rates Medallion Pipeline 💱

An automated cloud pipeline that pulls daily PHP exchange rates, stores them, models them and visualizes trends. Built to practice real data engineering beyond local scripts. This means cloud storage, cloud databases and scheduled orchestration.

![Tech Stack](https://img.shields.io/badge/-Python-3776AB?style=flat&logo=python&logoColor=white)
![Tech Stack](https://img.shields.io/badge/-Supabase-3ECF8E?style=flat&logo=supabase&logoColor=white)
![Tech Stack](https://img.shields.io/badge/-PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![Tech Stack](https://img.shields.io/badge/-GitHub%20Actions-2088FF?style=flat&logo=githubactions&logoColor=white)
![Tech Stack](https://img.shields.io/badge/-Power%20BI-F2C811?style=flat&logo=powerbi&logoColor=black)

---

## 📖 Overview

This pipeline pulls live PHP exchange rate data from a public API on a daily schedule. No manual steps are needed. It applies a Bronze/Silver/Gold architecture and publishes a live public dashboard. Compared to a purely local project, this one adds real cloud storage, a cloud database and unattended orchestration.

**This project demonstrates:**

- Scheduled automation with GitHub Actions, no server to maintain
- Cloud object storage and cloud Postgres
- Idempotent loading, safe to re-run without duplicates
- Secrets management through CI secrets
- Medallion architecture on a cloud-native stack

---

## 🏗️ Data Architecture

![Data Architecture](docs/architecture_diagram.png)

```
Frankfurter API (BSP reference rates)
        |
        v  extract.py
Raw JSON --> Supabase Storage (Bronze, date-partitioned)
        |
        v  load.py
silver_rates (Postgres)  -->  gold_rates_rolling (view)
        |
        v
Power BI dashboard (published, public link)

GitHub Actions runs the full pipeline daily.
```

1. **Bronze Layer**: Unmodified raw JSON from the API. Written to Supabase Storage and partitioned by date.
2. **Silver Layer**: Cleaned exchange rate records loaded into Postgres. Uses idempotent upserts and automated currency dimension seeding.
3. **Gold Layer**: A rolling average view for fast dashboard queries.

---

## 🛠️ Tech Stack & Rationale

| Layer              | Tool                            | Why                                              |
| ------------------ | ------------------------------- | ------------------------------------------------ |
| Source             | Frankfurter API                 | Free and no auth needed                          |
| Extract            | Python (`requests`)             | Simple HTTP pull                                 |
| Raw storage        | Supabase Storage                | Object storage for raw JSON, partitioned by date |
| Transform and Load | Python (`pandas`, `sqlalchemy`) | Cleans and loads data into Postgres              |
| Warehouse          | Supabase (Postgres)             | Silver table plus Gold view                      |
| Orchestration      | GitHub Actions                  | Free daily scheduling with no server             |
| Dashboard          | Power BI                        | Public dashboard with no login                   |

---

## 📸 Screenshots

<!-- Keep this to 2-4 images in docs/screenshots/. Priority: the live dashboard first, then a successful GitHub Actions run, then a sample Gold query result. -->

### Live dashboard

![Power BI dashboard](docs/screenshots/dashboard.png)

### Scheduled pipeline run

![GitHub Actions run](docs/screenshots/github_actions_run.png)

---

## 📂 Repository Structure

```
bsp-exchange-rate-pipeline/
│
├── src/
│   ├── extract.py
│   └── load.py
├── docs/
│   ├── architecture_diagram.png
│   └── screenshots/
├── .github/workflows/
├── .env.example
├── README.md
└── requirements.txt
```

---

## 🚀 Getting Started

### Prerequisites

- A Supabase project with a Storage bucket and Postgres database
- A GitHub repo with secrets set under Settings, Secrets and variables, Actions
- See `.env.example` for required variables

### Setup

```bash
git clone <repo>
cp .env.example .env
pip install -r requirements.txt
python src/extract.py
python src/load.py
```

The GitHub Actions workflow runs both scripts automatically once secrets are set.

---

## 🎯 Key Technical Decisions

- **Idempotent upserts over blind inserts.** A re-run never creates duplicate rows.
- **Bronze stored as raw JSON, not directly in Postgres.** This preserves the original response for reprocessing.
- **GitHub Actions over a dedicated orchestrator.** A single daily job does not need Airflow's DAG machinery.
- **A Gold view instead of a materialized table.** This is fast enough at this data volume and skips a refresh step.

---

## 📊 Results / Metrics

- **260,000+** historical exchange rate records processed and backfilled
- **3** analytical Gold views delivered
- Automated daily execution at **00:00 UTC**

---

## 🔗 Live Dashboard

[Add your published Power BI link here]

---

## 🧰 Skills Demonstrated

`Python` `REST APIs` `Supabase` `PostgreSQL` `Cloud Object Storage` `GitHub Actions` `CI/CD` `Medallion Architecture` `Idempotent ETL` `Secrets Management` `Power BI`
