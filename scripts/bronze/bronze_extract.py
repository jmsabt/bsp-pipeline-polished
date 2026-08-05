import json
import os
from datetime import date
from dotenv import load_dotenv
import requests
from supabase import create_client

load_dotenv()


def extract_daily_rates():
    today = date.today()
    url = "https://api.frankfurter.dev/v1/latest"
    storage_path = (
        f"raw/{today.year}/{today.month:02d}/rates_{today.isoformat()}.json"
    )

    print(f"[-->] Fetching latest daily exchange rates...")
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    payload = response.json()

    # Upload to Supabase Storage
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")
    bucket_name = os.getenv("SUPABASE_STORAGE_BUCKET", "raw-bsp-rates")

    client = create_client(supabase_url, supabase_key)
    payload_bytes = json.dumps(payload, indent=2).encode("utf-8")

    print(f"[-->] Uploading daily file to bucket: {storage_path}")
    client.storage.from_(bucket_name).upload(
        path=storage_path,
        file=payload_bytes,
        file_options={"content-type": "application/json", "upsert": "true"},
    )
    print("[✓] Daily Bronze extraction complete!")


if __name__ == "__main__":
    extract_daily_rates()