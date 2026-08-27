import pandas as pd
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing critical Supabase configuration in environment variables.")

def get_php_rates():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    all_rows = []
    page_size = 1000
    start = 0

    while True:
        response = (
            client.table("silver_rates")
            .select("rate_date, exchange_rate")
            .eq("target_currency", "PHP")
            .order("rate_date", desc=False)
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = response.data
        if not batch:
            break
        all_rows.extend(batch)
        start += page_size
        if len(batch) < page_size:
            break

    df = pd.DataFrame(all_rows)
    df["rate_date"] = pd.to_datetime(df["rate_date"])
    return df

def build_features(df):
    df = df.copy()
    df["prior_day_rate"] = df["exchange_rate"].shift(1)
    df["pct_daily_change"] = (
        (df["exchange_rate"] - df["prior_day_rate"]) / df["prior_day_rate"] * 100
    )
    df["rolling_7d_avg"] = df["exchange_rate"].rolling(window=7).mean()
    df["day_of_week"] = df["rate_date"].dt.dayofweek
    df["distance_from_7d_avg"] = df["exchange_rate"] - df["rolling_7d_avg"]

    df["next_day_rate"] = df["exchange_rate"].shift(-1)
    df["target"] = (df["next_day_rate"] > df["exchange_rate"]).astype(int)

    df = df.dropna().reset_index(drop=True)
    return df

if __name__ == "__main__":
    raw = get_php_rates()
    features = build_features(raw)
    print(features.tail())
    print(f"Total rows after feature engineering: {len(features)}")