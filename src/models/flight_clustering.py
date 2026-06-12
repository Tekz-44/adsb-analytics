"""
Flight behavior clustering.
Groups aircraft into behavioral categories using K-Means,
based on altitude, speed, vertical rate, and routing efficiency.

Expected clusters might include things like:
- Cruising traffic (high altitude, steady speed, low vertical rate)
- Approach/departure traffic (low-mid altitude, descending/climbing)
- Training/pattern aircraft (low altitude, low efficiency, lots of turns)
- Transiting traffic (high efficiency, straight paths)
"""

import psycopg2
import pandas as pd
import numpy as np
import math
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
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


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_aircraft_profiles(min_points=10):
    """
    Build one row per aircraft summarizing its flight behavior:
    - average altitude
    - average velocity
    - average |vertical rate|
    - routing efficiency
    - altitude range (max - min)
    """
    query = """
        SELECT callsign, icao24, latitude, longitude,
               baro_altitude, velocity, vertical_rate, collected_at
        FROM aircraft_states
        WHERE callsign IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND baro_altitude IS NOT NULL
          AND velocity IS NOT NULL
          AND vertical_rate IS NOT NULL
          AND on_ground = FALSE
          AND baro_altitude < 13000
        ORDER BY callsign, collected_at;
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()

    profiles = []
    for callsign, group in df.groupby("callsign"):
        if len(group) < min_points:
            continue

        points = group[["latitude", "longitude"]].values
        total_distance = sum(
            haversine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])
            for i in range(1, len(points))
        )
        straight_line = haversine(
            points[0][0], points[0][1], points[-1][0], points[-1][1]
        )
        efficiency = straight_line / total_distance if total_distance > 0 else 0

        profiles.append({
            "callsign": callsign.strip(),
            "points": len(group),
            "avg_altitude": group["baro_altitude"].mean(),
            "avg_velocity": group["velocity"].mean(),
            "avg_vrate_abs": group["vertical_rate"].abs().mean(),
            "altitude_range": group["baro_altitude"].max() - group["baro_altitude"].min(),
            "efficiency": min(efficiency, 1.0)
        })

    return pd.DataFrame(profiles)


def cluster_aircraft(n_clusters=4):
    df = build_aircraft_profiles()
    print(f"Built profiles for {len(df)} aircraft.")

    features = ["avg_altitude", "avg_velocity", "avg_vrate_abs",
                "altitude_range", "efficiency"]
    X = df[features]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster"] = kmeans.fit_predict(X_scaled)

    return df, features


def describe_clusters(df, features):
    """Print summary statistics for each cluster to interpret them."""
    print(f"\n=== Cluster Profiles ===\n")

    for cluster_id in sorted(df["cluster"].unique()):
        subset = df[df["cluster"] == cluster_id]
        print(f"Cluster {cluster_id} — {len(subset)} aircraft")
        print(f"  Avg altitude:    {subset['avg_altitude'].mean():.0f}m")
        print(f"  Avg velocity:    {subset['avg_velocity'].mean():.1f} m/s")
        print(f"  Avg |v-rate|:    {subset['avg_vrate_abs'].mean():.2f} m/s")
        print(f"  Avg alt range:   {subset['altitude_range'].mean():.0f}m")
        print(f"  Avg efficiency:  {subset['efficiency'].mean():.3f}")

        examples = subset["callsign"].head(5).tolist()
        print(f"  Examples:        {', '.join(examples)}")
        print()


if __name__ == "__main__":
    df, features = cluster_aircraft(n_clusters=4)
    describe_clusters(df, features)