"""
Congestion prediction.
Predicts aircraft congestion levels around KDTW based on
time-of-day and day-of-week patterns.

Since OpenSky doesn't provide actual flight delay data, we use
aircraft density (unique aircraft per time window) as a proxy
for congestion -- higher density generally correlates with
higher delay risk.
"""

import psycopg2
import pandas as pd
import numpy as np
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "adsb"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def build_congestion_dataset():
    """
    Aggregate raw aircraft states into 5-minute windows,
    counting unique aircraft per window -- our congestion metric.
    """
    query = """
        SELECT
            date_trunc('minute', collected_at)
                - (EXTRACT(MINUTE FROM collected_at)::int % 5) * interval '1 minute'
                AS time_window,
            COUNT(DISTINCT icao24) AS aircraft_count
        FROM aircraft_states
        WHERE on_ground = FALSE
        GROUP BY time_window
        ORDER BY time_window;
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def add_time_features(df):
    """Extract time-based features for the model."""
    df["time_window"] = pd.to_datetime(df["time_window"])
    df["hour"] = df["time_window"].dt.hour
    df["minute"] = df["time_window"].dt.minute
    df["day_of_week"] = df["time_window"].dt.dayofweek
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    return df


def train_congestion_model():
    df = build_congestion_dataset()
    print(f"Built {len(df)} time windows from raw data.")

    df = add_time_features(df)

    features = ["hour", "minute", "day_of_week", "hour_sin", "hour_cos"]
    X = df[features]
    y = df["aircraft_count"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"\n=== Model Performance ===")
    print(f"  Mean Absolute Error: {mae:.2f} aircraft")
    print(f"  R² Score:            {r2:.3f}")

    # Feature importance
    importance = pd.Series(model.feature_importances_, index=features)
    importance = importance.sort_values(ascending=False)

    print(f"\n=== Feature Importance ===")
    for feat, imp in importance.items():
        bar = "█" * int(imp * 50)
        print(f"  {feat:<12} {imp:.3f} {bar}")

    return model, df


def predict_hourly_congestion(model):
    """Predict average congestion for each hour of the day."""
    hours = range(24)
    predictions = []

    for hour in hours:
        # Use Wednesday (day_of_week=2) as a typical weekday, minute=0
        row = pd.DataFrame([{
            "hour": hour,
            "minute": 0,
            "day_of_week": 2,
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24)
        }])
        pred = model.predict(row)[0]
        predictions.append((hour, pred))

    return predictions


if __name__ == "__main__":
    model, df = train_congestion_model()

    print(f"\n=== Predicted Congestion by Hour (typical weekday) ===")
    predictions = predict_hourly_congestion(model)
    max_pred = max(p[1] for p in predictions)

    for hour, pred in predictions:
        bar = "█" * int((pred / max_pred) * 30)
        print(f"  {hour:02d}:00  {bar} {pred:.1f} aircraft")