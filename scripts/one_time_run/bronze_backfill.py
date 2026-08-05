import json
import os
from datetime import date
from dotenv import load_dotenv
import requests
from supabase import create_client

load_dotenv()


def run_full_backfill():
    # Frankfurter API historical start date
    START_DATE = "1999-01-04"
    today = date.today().isoformat()

    # Query range from 1999 to today
    url = f"https://api.frankfurter.dev/v1/{START_DATE}.."
    storage_path = f"backfills/rates_full_{START_DATE}_to_{today}.json"

    print(f"[-->] Fetching entire historical dataset from {START_DATE}...")
    # Timeout set to 30s to allow the larger payload (~3-4 MB) to finish downloading
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()

    # Upload to Supabase Storage
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")
    bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "raw-bsp-rates")

    client = create_client(supabase_url, supabase_key)
    payload_bytes = json.dumps(payload, indent=2).encode("utf-8")

    print(f"[-->] Uploading full history to Bronze bucket: {storage_path}")
    client.storage.from_(bucket_name).upload(
        path=storage_path,
        file=payload_bytes,
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    print(f"[✓] Backfill complete! Retained records from {START_DATE} to {today}.")


if __name__ == "__main__":
    run_full_backfill()