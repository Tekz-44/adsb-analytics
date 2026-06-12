"""
Anomaly detection.
Uses Isolation Forest to flag aircraft states that look unusual
compared to normal traffic patterns around KDTW.

Features used:
- altitude
- velocity
- vertical rate
- true track (heading)
"""

import psycopg2
import pandas as pd
import numpy as np
import os
from sklearn.ensemble import IsolationForest
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


def fetch_features():
    """Fetch the features we'll use for anomaly detection."""
    query = """
        SELECT id, callsign, icao24, baro_altitude, velocity,
               vertical_rate, true_track, on_ground, collected_at
        FROM aircraft_states
        WHERE on_ground = FALSE
          AND baro_altitude IS NOT NULL
          AND velocity IS NOT NULL
          AND vertical_rate IS NOT NULL
          AND true_track IS NOT NULL;
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def detect_anomalies(contamination=0.02):
    """
    Run Isolation Forest on flight data to find anomalous states.

    contamination: expected proportion of anomalies (2% default)
    """
    df = fetch_features()
    print(f"Analyzing {len(df)} aircraft state records...")

    # Features for the model
    features = df[["baro_altitude", "velocity", "vertical_rate", "true_track"]]

    # Train the model
    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )
    df["anomaly"] = model.fit_predict(features)
    df["anomaly_score"] = model.decision_function(features)

    # -1 means anomaly, 1 means normal
    anomalies = df[df["anomaly"] == -1].sort_values("anomaly_score")

    return df, anomalies


if __name__ == "__main__":
    df, anomalies = detect_anomalies()

    print(f"\n=== Anomaly Detection Results ===")
    print(f"Total records analyzed: {len(df)}")
    print(f"Anomalies detected:      {len(anomalies)} "
          f"({len(anomalies)/len(df)*100:.1f}%)")

    print(f"\n=== Top 15 Most Anomalous States ===")
    print(f"{'Callsign':<12} {'Alt (m)':<10} {'Velocity':<10} "
          f"{'V-Rate':<10} {'Track':<8} {'Score':<8} Time")
    print("-" * 80)

    for _, row in anomalies.head(15).iterrows():
        callsign = (row["callsign"] or "UNKNOWN").strip()
        print(f"{callsign:<12} {row['baro_altitude']:<10.1f} "
              f"{row['velocity']:<10.1f} {row['vertical_rate']:<10.1f} "
              f"{row['true_track']:<8.1f} {row['anomaly_score']:<8.3f} "
              f"{row['collected_at'].strftime('%H:%M:%S')}")