import json
import os
import sys
from datetime import date
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
from supabase import create_client

load_dotenv()

# RUN python scripts/silver/silver_load.py "backfills/rates_full_1999-01-04_to_2026-08-05.json" FOR BACKFILL

# Initialize Supabase Client (Storage) and Postgres Connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "raw-bsp-rates")
DATABASE_URL = os.getenv("SUPABASE_DB_URL")


def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_json_from_storage(client, storage_path: str) -> dict:
    """Downloads a JSON file from Supabase Storage into memory."""
    print(f"[-->] Downloading file from bucket: {storage_path}")
    response_bytes = client.storage.from_(BUCKET_NAME).download(storage_path)
    return json.loads(response_bytes.decode("utf-8"))


def parse_and_flatten_rates(payload: dict) -> tuple[set, list[tuple]]:
    """
    Handles both nested backfill structures and flat daily API structures.
    """
    base_currency = payload.get("base", "EUR")
    rates_data = payload.get("rates", {})
    
    currencies_found = {base_currency}
    flat_records = []

    # Case 1: Single-day API response (e.g., {"rates": {"USD": 1.08}, "date": "2026-08-05"})
    if "date" in payload and isinstance(next(iter(rates_data.values()), None), (int, float)):
        rate_date = payload["date"]
        for target_currency, rate in rates_data.items():
            currencies_found.add(target_currency)
            flat_records.append((rate_date, base_currency, target_currency, float(rate)))
            
    # Case 2: Multi-day backfill response (e.g., {"rates": {"2026-08-05": {"USD": 1.08}}})
    else:
        for rate_date, target_dict in rates_data.items():
            if isinstance(target_dict, dict):
                for target_currency, rate in target_dict.items():
                    currencies_found.add(target_currency)
                    flat_records.append((rate_date, base_currency, target_currency, float(rate)))

    return currencies_found, flat_records


def seed_missing_currencies(conn, currencies: set):
    """Ensures foreign key requirements are met in dim_currencies."""
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
    """Batch upserts flat exchange rates into silver_rates idempotently."""
    query = """
        INSERT INTO silver_rates (rate_date, base_currency, target_currency, exchange_rate)
        VALUES %s
        ON CONFLICT (rate_date, base_currency, target_currency)
        DO UPDATE SET
            exchange_rate = EXCLUDED.exchange_rate,
            ingested_at = CURRENT_TIMESTAMP;
    """
    with conn.cursor() as cur:
        # Page size of 10,000 for fast batch ingestion
        execute_values(cur, query, records, page_size=10000)
    conn.commit()


def run_silver_transformation(target_file_path: str = None):
    # 1. Resolve storage target path if not explicitly provided
    if not target_file_path:
        today = date.today()
        target_file_path = (
            f"raw/{today.year}/{today.month:02d}/rates_{today.isoformat()}.json"
        )

    # 2. Connect to services
    supabase_client = get_supabase_client()
    conn = psycopg2.connect(DATABASE_URL)

    try:
        # 3. Read and parse Bronze JSON
        payload = fetch_json_from_storage(supabase_client, target_file_path)
        currencies, records = parse_and_flatten_rates(payload)

        print(
            f"[-->] Extracted {len(records):,} records spanning {len(currencies)} currencies."
        )

        # 4. Seed metadata dimensions and bulk load Silver fact table
        seed_missing_currencies(conn, currencies)
        print("[-->] Upserting records into Postgres silver_rates...")
        upsert_silver_rates(conn, records)

        print(
            f"[✓] Silver transformation complete for: {target_file_path}"
        )

    except Exception as e:
        conn.rollback()
        print(f"[X] Error executing Silver transformation: {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    # If a file path is passed as a CLI argument, process that file (Backfill).
    # Otherwise, default to today's daily file.
    if len(sys.argv) > 1:
        run_silver_transformation(sys.argv[1])
    else:
        run_silver_transformation()