import os
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, confusion_matrix
from features import get_php_rates, build_features

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "model.pkl")
SCALER_PATH = os.path.join(SCRIPT_DIR, "scaler.pkl")

TRAIN_END_DATE = "2023-12-31"
TEST_START_DATE = "2024-01-01"

FEATURE_COLUMNS = [
    "prior_day_rate",
    "pct_daily_change",
    "rolling_7d_avg",
    "day_of_week",
    "distance_from_7d_avg",
]

def split_data(df):
    train_df = df[df["rate_date"] <= TRAIN_END_DATE]
    test_df = df[df["rate_date"] >= TEST_START_DATE]
    return train_df, test_df

def naive_baseline_predict(df):
    prior_direction = (df["exchange_rate"] > df["prior_day_rate"]).astype(int)
    return prior_direction

def train_logistic_regression(train_df):
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df["target"]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train_scaled, y_train)
    return model, scaler

def train_random_forest(train_df):
    # Random Forest does not need feature scaling, since it splits on raw thresholds, not distances.
    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df["target"]

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=5,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model

def evaluate(y_true, y_pred, label):
    acc = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)
    print(f"\n--- {label} ---")
    print(f"Accuracy: {acc:.4f}")
    print("Confusion Matrix:")
    print(cm)
    return acc

if __name__ == "__main__":
    raw = get_php_rates()
    features = build_features(raw)

    train_df, test_df = split_data(features)
    print(f"Train rows: {len(train_df)}, Test rows: {len(test_df)}")

    # Baseline
    baseline_preds = naive_baseline_predict(test_df)
    evaluate(test_df["target"], baseline_preds, "Naive Baseline")

    # Logistic Regression
    lr_model, scaler = train_logistic_regression(train_df)
    X_test = test_df[FEATURE_COLUMNS]
    X_test_scaled = scaler.transform(X_test)
    lr_preds = lr_model.predict(X_test_scaled)
    evaluate(test_df["target"], lr_preds, "Logistic Regression")

    # Random Forest
    rf_model = train_random_forest(train_df)
    rf_preds = rf_model.predict(X_test)
    evaluate(test_df["target"], rf_preds, "Random Forest")

    # Save Logistic Regression as the primary model for predict.py
    joblib.dump(lr_model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"\nModel saved to {MODEL_PATH}")
    print(f"Scaler saved to {SCALER_PATH}")