import json
import logging
import os
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
from supabase import Client, create_client

# 1. Structured Logging: Use standard logging over print statements for observability in production orchestrators (Airflow, Prefect).
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# 2. Config & Secrets Management: Fail fast if critical environment variables are missing.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "raw-bsp-rates")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing critical Supabase configuration in environment variables.")


# 3. Connection Pooling/Reuse: Instantiate external SDK clients globally or pass them in to avoid re-creation on every run.
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_daily_rates(execution_date: str | None = None) -> None:
    """
    Extracts daily exchange rates and uploads raw JSON to Data Lake storage.
    
    4. Idempotency & Backfills: Allow passing an explicit execution date (YYYY-MM-DD). 
    Avoid relying purely on `date.today()`, which fails historical backfills and shifts across time zones.
    """
    if execution_date:
        run_date = datetime.strptime(execution_date, "%Y-%m-%d").date()
    else:
        run_date = datetime.now(timezone.utc).date()

    # 5. Partition Strategy: Partition paths by Year/Month/Day ( Hive-style: year=YYYY/month=MM/day=DD ) 
    # to optimize downstream query engine pruning (e.g., DuckDB, Snowflake).
    iso_date = run_date.isoformat()
    storage_path = f"raw/year={run_date.year}/month={run_date.month:02d}/rates_{iso_date}.json"

    # API request targeting the specific date for determinism
    url = f"https://api.frankfurter.dev/v1/{iso_date}"

    logger.info(f"Fetching exchange rates for {iso_date}...")
    
    # 6. Resilience: Use strict timeouts and handle request exceptions explicitly.
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch data from Frankfurter API: {e}")
        raise

    # 7. Raw Lake Storage: Save raw payloads as unformatted, compact JSON (indent=None) to save bandwidth/storage.
    payload_bytes = json.dumps(payload).encode("utf-8")

    logger.info(f"Uploading Bronze raw file to {BUCKET_NAME}/{storage_path}")
    try:
        supabase_client.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=payload_bytes,
            # Upsert ensures re-running the job updates existing data without throwing errors (Idempotent write)
            file_options={"content-type": "application/json", "upsert": "true"},
        )
        logger.info("Daily Bronze extraction complete!")
    except Exception as e:
        logger.error(f"Failed to upload raw JSON to object storage: {e}")
        raise


if __name__ == "__main__":
    extract_daily_rates()