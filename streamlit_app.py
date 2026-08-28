import os
import pandas as pd
import streamlit as st
from datetime import date, timedelta
from supabase import create_client
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or st.secrets.get("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase configuration. Check environment variables.")
    st.stop()

client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="EUR/PHP Direction Forecast", layout="wide")
st.markdown("""
    <style>
    .stMetric {
        background-color: #1A1D23;
        border: 1px solid #2A2E37;
        border-radius: 10px;
        padding: 16px;
    }
    .stMetric label {
        color: #A0A4AB !important;
    }
    [data-testid="stMetricValue"] {
        color: #FFC20E;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #2A2E37;
        border-radius: 10px;
    }
    hr {
        border-color: #2A2E37;
    }

    .block-container {
    max-width: 1100px;
    margin: 0 auto;
    }

    @media (max-width: 640px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 2rem;
        }
        h1 {
            font-size: 1.5rem !important;
        }
        h3 {
            font-size: 1.1rem !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
        }
    }
    </style>
""", unsafe_allow_html=True)
st.title("EUR/PHP Next-Day Direction Forecast")
st.caption("Experimental model output. Not financial advice.")


@st.cache_data(ttl=3600)
def get_recent_rates(days=30):
    cutoff = (date.today() - timedelta(days=days + 10)).isoformat()
    response = (
        client.table("silver_rates")
        .select("rate_date, exchange_rate")
        .eq("target_currency", "PHP")
        .gte("rate_date", cutoff)
        .order("rate_date", desc=False)
        .execute()
    )
    df = pd.DataFrame(response.data)
    df["rate_date"] = pd.to_datetime(df["rate_date"])
    return df.tail(days)


@st.cache_data(ttl=3600)
def get_predictions(limit=30):
    response = (
        client.table("ml_predictions")
        .select("rate_date, predicted_direction, confidence, actual_direction")
        .order("rate_date", desc=True)
        .limit(limit)
        .execute()
    )
    df = pd.DataFrame(response.data)
    if df.empty:
        return df
    df["rate_date"] = pd.to_datetime(df["rate_date"])
    return df.sort_values("rate_date", ascending=False).reset_index(drop=True)


rates_df = get_recent_rates()
predictions_df = get_predictions()

if predictions_df.empty:
    st.warning("No predictions found yet.")
    st.stop()

latest_prediction = predictions_df.iloc[0]

col1, col2, col3 = st.columns(3)

with col1:
    direction = latest_prediction["predicted_direction"]
    st.metric(
        label=f"Prediction for {latest_prediction['rate_date'].date()}",
        value=direction,
    )

with col2:
    st.metric(
        label="Model Confidence",
        value=f"{latest_prediction['confidence'] * 100:.1f}%",
    )

with col3:
    resolved = predictions_df[predictions_df["actual_direction"].notna()]
    if len(resolved) > 0:
        correct_count = (resolved["predicted_direction"] == resolved["actual_direction"]).sum()
        total_count = len(resolved)
        accuracy = correct_count / total_count * 100
        st.metric(label="Rolling Accuracy", value=f"{accuracy:.1f}%", help=f"Based on {total_count} resolved predictions")
    else:
        st.metric(label="Rolling Accuracy", value="N/A")

st.divider()

chart_col, table_col = st.columns([2, 1])

with chart_col:
    st.subheader("EUR/PHP Rate, Last 30 Days")
    st.line_chart(rates_df.set_index("rate_date")["exchange_rate"])

with table_col:
    st.subheader("Recent Predictions")
    history_df = predictions_df.copy()
    history_df["rate_date"] = history_df["rate_date"].dt.date
    history_df["correct"] = history_df.apply(
        lambda row: "Yes" if row["actual_direction"] == row["predicted_direction"]
        else ("Pending" if pd.isna(row["actual_direction"]) else "No"),
        axis=1,
    )
    history_df = history_df.rename(columns={
        "rate_date": "Date",
        "predicted_direction": "Pred.",
        "actual_direction": "Actual",
        "confidence": "Conf.",
        "correct": "Correct",
    })
    history_df["Conf."] = (history_df["Conf."] * 100).round(1).astype(str) + "%"
    st.dataframe(
        history_df[["Date", "Pred.", "Actual", "Conf.", "Correct"]].head(7),
        use_container_width=True,
        hide_index=True,
    )

st.caption("This model is experimental and intended for demonstration purposes only. It should not be used as the sole basis for financial decisions.")