import json
import os
import sys
import traceback
from datetime import date
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
from supabase import create_client

load_dotenv()

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "raw-bsp-rates")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")

if not DATABASE_URL:
    raise ValueError("[X] Database connection URL is missing from .env!")


def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------------------------------------------------------
# PIPELINE LOGGING FUNCTIONS (CONTROL PLANE)
# -----------------------------------------------------------------------------
def log_pipeline_start(conn, pipeline_name: str, run_type: str, target_file: str) -> int:
    """Inserts an initial execution record in RUNNING status."""
    query = """
        INSERT INTO pipeline_logs (pipeline_name, run_type, target_file, status)
        VALUES (%s, %s, %s, 'RUNNING')
        RETURNING log_id;
    """
    with conn.cursor() as cur:
        cur.execute(query, (pipeline_name, run_type, target_file))
        log_id = cur.fetchone()[0]
    conn.commit()
    return log_id


def log_pipeline_end(conn, log_id: int, status: str, records_processed: int = 0, error_message: str = None):
    """Updates log record upon SUCCESS or FAILED completion with duration."""
    query = """
        UPDATE pipeline_logs
        SET status = %s,
            records_processed = %s,
            error_message = %s,
            ended_at = CURRENT_TIMESTAMP,
            duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))
        WHERE log_id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (status, records_processed, error_message, log_id))
    conn.commit()


# -----------------------------------------------------------------------------
# DATA TRANSFORMATION & LOADING (DATA PLANE)
# -----------------------------------------------------------------------------
def fetch_json_from_storage(client, storage_path: str) -> dict:
    print(f"[-->] Downloading file from bucket: {storage_path}")
    response_bytes = client.storage.from_(BUCKET_NAME).download(storage_path)
    return json.loads(response_bytes.decode("utf-8"))


def parse_and_flatten_rates(payload: dict) -> tuple[set, list[tuple]]:
    base_currency = payload.get("base", "EUR")
    rates_data = payload.get("rates", {})
    
    currencies_found = {base_currency}
    flat_records = []

    # Handle single-day API response structure
    if "date" in payload and isinstance(next(iter(rates_data.values()), None), (int, float)):
        rate_date = payload["date"]
        for target_currency, rate in rates_data.items():
            currencies_found.add(target_currency)
            flat_records.append((rate_date, base_currency, target_currency, float(rate)))
            
    # Handle multi-day backfill API response structure
    else:
        for rate_date, target_dict in rates_data.items():
            if isinstance(target_dict, dict):
                for target_currency, rate in target_dict.items():
                    currencies_found.add(target_currency)
                    flat_records.append((rate_date, base_currency, target_currency, float(rate)))

    return currencies_found, flat_records


def seed_missing_currencies(conn, currencies: set):
    query = """
        INSERT INTO dim_currencies (currency_code, currency_name)
        VALUES %s
        ON CONFLICT (currency_code) DO NOTHING;
    """
    records = [(code, code) for code in currencies]
    with conn.cursor() as cur:
        execute_values(cur, query, records)
    conn.commit()


def upsert_silver_rates(conn, records: list[tuple]):
    query = """
        INSERT INTO silver_rates (rate_date, base_currency, target_currency, exchange_rate)
        VALUES %s
        ON CONFLICT (rate_date, base_currency, target_currency)
        DO UPDATE SET
            exchange_rate = EXCLUDED.exchange_rate,
            ingested_at = CURRENT_TIMESTAMP;
    """
    with conn.cursor() as cur:
        execute_values(cur, query, records, page_size=10000)
    conn.commit()


# -----------------------------------------------------------------------------
# MAIN PIPELINE EXECUTION
# -----------------------------------------------------------------------------
def run_silver_transformation(target_file_path: str = None):
    pipeline_name = "silver_exchange_rates_load"
    run_type = "BACKFILL" if target_file_path else "DAILY"

    if not target_file_path:
        today = date.today()
        target_file_path = f"raw/{today.year}/{today.month:02d}/rates_{today.isoformat()}.json"

    supabase_client = get_supabase_client()
    conn = psycopg2.connect(DATABASE_URL)
    
    # 1. Start execution log
    log_id = log_pipeline_start(conn, pipeline_name, run_type, target_file_path)

    try:
        # 2. Execute extraction and transformation
        payload = fetch_json_from_storage(supabase_client, target_file_path)
        currencies, records = parse_and_flatten_rates(payload)

        print(f"[-->] Extracted {len(records):,} records spanning {len(currencies)} currencies.")

        # 3. Database loads
        seed_missing_currencies(conn, currencies)
        print("[-->] Upserting records into Postgres silver_rates...")
        upsert_silver_rates(conn, records)

        # 4. Log SUCCESS
        log_pipeline_end(conn, log_id, status="SUCCESS", records_processed=len(records))
        print(f"[✓] Silver transformation complete for: {target_file_path}")

    except Exception as e:
        conn.rollback()
        err_msg = traceback.format_exc()
        print(f"[X] Error executing Silver transformation: {e}")
        
        # 5. Log FAILED with error trace
        try:
            log_pipeline_end(conn, log_id, status="FAILED", error_message=err_msg)
        except Exception as log_err:
            print(f"[X] Failed to log error to database: {log_err}")
            
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_silver_transformation(sys.argv[1])
    else:
        run_silver_transformation()