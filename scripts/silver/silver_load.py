import json
import logging
import os
import sys
from datetime import datetime, timezone
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
from supabase import Client, create_client

# 1. Observability: Use structured logging for execution traces instead of standard print statements.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

# Config & Environment Validation
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "raw-bsp-rates")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")

if not DATABASE_URL or not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("[X] Missing critical database or Supabase configuration in environment variables.")

# 2. Connection Reuse: Keep external SDK clients stateful outside functions where applicable.
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# 3. Context Managers: Ensure DB connections & cursors auto-close and handle rollbacks cleanly.
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# PIPELINE LOGGING (CONTROL PLANE)
# -----------------------------------------------------------------------------
def log_pipeline_start(cursor, pipeline_name: str, run_type: str, target_file: str) -> int:
    """Inserts an initial execution record into metadata tracking."""
    # 4. Decoupled Control Plane: Avoid inline conn.commit() inside log functions; manage transactions cleanly.
    query = """
        INSERT INTO pipeline_logs (pipeline_name, run_type, target_file, status)
        VALUES (%s, %s, %s, 'RUNNING')
        RETURNING log_id;
    """
    cursor.execute(query, (pipeline_name, run_type, target_file))
    return cursor.fetchone()[0]


def log_pipeline_end(cursor, log_id: int, status: str, records_processed: int = 0, error_message: str = None) -> None:
    """Updates log record upon SUCCESS or FAILED state."""
    query = """
        UPDATE pipeline_logs
        SET status = %s,
            records_processed = %s,
            error_message = %s,
            ended_at = CURRENT_TIMESTAMP,
            duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))
        WHERE log_id = %s;
    """
    cursor.execute(query, (status, records_processed, error_message, log_id))


# -----------------------------------------------------------------------------
# DATA TRANSFORMATION & LOADING (DATA PLANE)
# -----------------------------------------------------------------------------
def fetch_json_from_storage(client: Client, storage_path: str) -> dict:
    logger.info(f"Downloading file from object storage: {storage_path}")
    try:
        response_bytes = client.storage.from_(BUCKET_NAME).download(storage_path)
        return json.loads(response_bytes.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to fetch or parse file '{storage_path}' from bucket '{BUCKET_NAME}': {e}")
        raise


def parse_and_flatten_rates(payload: dict) -> tuple[set[str], list[tuple[str, str, str, float]]]:
    """
    5. Pure Function Transformations: Decouple parsing/flattening logic entirely from storage and database logic.
    This enables fast, simple unit testing without mocking external interfaces.
    """
    base_currency = payload.get("base", "EUR")
    rates_data = payload.get("rates", {})
    
    currencies_found = {base_currency}
    flat_records = []

    # Handle single-day payload schema
    if "date" in payload and isinstance(next(iter(rates_data.values()), None), (int, float)):
        rate_date = payload["date"]
        for target_currency, rate in rates_data.items():
            currencies_found.add(target_currency)
            flat_records.append((rate_date, base_currency, target_currency, float(rate)))
            
    # Handle multi-day payload schema
    else:
        for rate_date, target_dict in rates_data.items():
            if isinstance(target_dict, dict):
                for target_currency, rate in target_dict.items():
                    currencies_found.add(target_currency)
                    flat_records.append((rate_date, base_currency, target_currency, float(rate)))

    return currencies_found, flat_records


def seed_missing_currencies(cursor, currencies: set[str]) -> None:
    """Seeds dimension tables prior to loading fact data."""
    query = """
        INSERT INTO dim_currencies (currency_code, currency_name)
        VALUES %s
        ON CONFLICT (currency_code) DO NOTHING;
    """
    records = [(code, code) for code in currencies]
    execute_values(cursor, query, records)


def upsert_silver_rates(cursor, records: list[tuple[str, str, str, float]]) -> None:
    """
    6. Idempotence via Bulk Upsert: Batch loads using `execute_values` with `ON CONFLICT DO UPDATE`
    guarantees re-running pipelines will not produce duplicate rows or trigger unique key violations.
    """
    query = """
        INSERT INTO silver_rates (rate_date, base_currency, target_currency, exchange_rate)
        VALUES %s
        ON CONFLICT (rate_date, base_currency, target_currency)
        DO UPDATE SET
            exchange_rate = EXCLUDED.exchange_rate,
            ingested_at = CURRENT_TIMESTAMP;
    """
    execute_values(cursor, query, records, page_size=5000)


# -----------------------------------------------------------------------------
# MAIN PIPELINE EXECUTION
# -----------------------------------------------------------------------------
def run_silver_transformation(target_file_path: str | None = None) -> None:
    pipeline_name = "silver_exchange_rates_load"
    run_type = "BACKFILL" if target_file_path else "DAILY"

    # 7. Partition Support: Accommodate modern Hive-style storage paths or default to deterministic daily path
    if not target_file_path:
        run_date = datetime.now(timezone.utc).date()
        target_file_path = f"raw/year={run_date.year}/month={run_date.month:02d}/rates_{run_date.isoformat()}.json"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 8. Transaction Control: Start control logging within the current transaction context
            log_id = log_pipeline_start(cur, pipeline_name, run_type, target_file_path)
            conn.commit()

            try:
                # Extract and Transform Data Plane
                payload = fetch_json_from_storage(supabase_client, target_file_path)
                currencies, records = parse_and_flatten_rates(payload)

                logger.info(f"Extracted {len(records):,} records across {len(currencies)} currencies.")

                # Load Data Plane
                seed_missing_currencies(cur, currencies)
                logger.info("Upserting records into PostgreSQL silver_rates...")
                upsert_silver_rates(cur, records)

                # Update Control Plane
                log_pipeline_end(cur, log_id, status="SUCCESS", records_processed=len(records))
                conn.commit()
                logger.info(f"Silver transformation successfully completed for: {target_file_path}")

            except Exception as e:
                conn.rollback()
                
                # 9. Isolated Error Reporting: Capture failure log using a separate transaction attempt
                logger.error(f"Error executing Silver transformation: {e}", exc_info=True)
                try:
                    with conn.cursor() as log_cur:
                        log_pipeline_end(log_cur, log_id, status="FAILED", error_message=str(e))
                    conn.commit()
                except Exception as log_err:
                    logger.critical(f"Failed to record failure state in database logs: {log_err}")
                    
                raise e


if __name__ == "__main__":
    file_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_silver_transformation(file_arg)