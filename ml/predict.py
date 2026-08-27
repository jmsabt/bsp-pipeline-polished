import os
import joblib
import pandas as pd
from datetime import timedelta
from supabase import create_client
from dotenv import load_dotenv
from features import get_php_rates, build_features

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing critical Supabase configuration in environment variables.")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "model.pkl")
SCALER_PATH = os.path.join(SCRIPT_DIR, "scaler.pkl")

FEATURE_COLUMNS = [
    "prior_day_rate",
    "pct_daily_change",
    "rolling_7d_avg",
    "day_of_week",
    "distance_from_7d_avg",
]

MODEL_VERSION = "logreg_v1"

client = create_client(SUPABASE_URL, SUPABASE_KEY)


def load_model():
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def build_latest_features(raw_df):
    """
    Builds features up through the most recent available rate.
    Unlike build_features in features.py, this keeps the final row,
    since that row is what we predict tomorrow from. It has no
    target, since tomorrow has not happened yet.
    """
    df = raw_df.copy()
    df["prior_day_rate"] = df["exchange_rate"].shift(1)
    df["pct_daily_change"] = (
        (df["exchange_rate"] - df["prior_day_rate"]) / df["prior_day_rate"] * 100
    )
    df["rolling_7d_avg"] = df["exchange_rate"].rolling(window=7).mean()
    df["day_of_week"] = df["rate_date"].dt.dayofweek
    df["distance_from_7d_avg"] = df["exchange_rate"] - df["rolling_7d_avg"]
    df = df.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
    return df


def predict_tomorrow():
    model, scaler = load_model()
    raw = get_php_rates()
    features = build_latest_features(raw)

    latest_row = features.iloc[[-1]]
    latest_date = latest_row["rate_date"].iloc[0]
    target_date = (latest_date + timedelta(days=1)).date().isoformat()

    X_latest = latest_row[FEATURE_COLUMNS]
    X_latest_scaled = scaler.transform(X_latest)

    pred_class = model.predict(X_latest_scaled)[0]
    pred_proba = model.predict_proba(X_latest_scaled)[0]

    predicted_direction = "UP" if pred_class == 1 else "DOWN"
    confidence = float(pred_proba[pred_class])

    print(f"Latest known rate date: {latest_date.date()}")
    print(f"Predicting for: {target_date}")
    print(f"Predicted direction: {predicted_direction}")
    print(f"Confidence: {confidence:.4f}")

    existing = (
        client.table("ml_predictions")
        .select("id")
        .eq("rate_date", target_date)
        .execute()
    )

    if existing.data:
        print(f"Prediction for {target_date} already exists. Skipping insert.")
        return

    client.table("ml_predictions").insert({
        "rate_date": target_date,
        "predicted_direction": predicted_direction,
        "confidence": round(confidence, 4),
        "actual_direction": None,
        "model_version": MODEL_VERSION,
    }).execute()

    print(f"Prediction for {target_date} saved.")


def backfill_actuals():
    """
    Finds predictions where actual_direction is still NULL, and where
    we now have real rate data for that date, then fills in whether
    the prediction was correct.
    """
    raw = get_php_rates()
    raw = raw.sort_values("rate_date").reset_index(drop=True)
    raw["prior_day_rate"] = raw["exchange_rate"].shift(1)
    raw["actual_direction"] = raw.apply(
        lambda row: "UP" if row["exchange_rate"] > row["prior_day_rate"] else "DOWN",
        axis=1,
    )
    raw["rate_date_str"] = raw["rate_date"].dt.date.astype(str)

    pending = (
        client.table("ml_predictions")
        .select("id, rate_date")
        .is_("actual_direction", "null")
        .execute()
    )

    if not pending.data:
        print("No pending predictions to backfill.")
        return

    updated_count = 0
    for row in pending.data:
        match = raw[raw["rate_date_str"] == row["rate_date"]]
        if match.empty:
            continue

        actual = match.iloc[0]["actual_direction"]
        client.table("ml_predictions").update({
            "actual_direction": actual
        }).eq("id", row["id"]).execute()
        updated_count += 1

    print(f"Backfilled {updated_count} prediction(s) with actual outcomes.")


if __name__ == "__main__":
    backfill_actuals()
    predict_tomorrow()