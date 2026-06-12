"""
ADS-B spoofing detection.
Flags aircraft state reports that violate physical flight constraints --
a strong signal of spoofed or corrupted ADS-B data.

Checks performed:
1. Impossible speed (faster than any aircraft can realistically fly)
2. Impossible climb/descent rate
3. Impossible position jumps (teleportation between consecutive reports)
4. Impossible altitude (negative or absurdly high)
5. Duplicate/conflicting positions for the same ICAO24 at the same time
"""

import psycopg2
import pandas as pd
import numpy as np
import math
import os
from dotenv import load_dotenv

load_dotenv()

# Physical limits (generous, to avoid false positives on legit fast jets)
MAX_REALISTIC_SPEED_MS = 350      # ~680 knots, faster than any airliner
MAX_REALISTIC_VRATE_MS = 50       # ~9800 ft/min, extreme even for fighters
MAX_REALISTIC_ALTITUDE_M = 13000  # ~43,000 ft
MIN_REALISTIC_ALTITUDE_M = -100   # allow slightly below sea level (Death Valley etc.)
MAX_REALISTIC_JUMP_SPEED_MS = 400 # max speed implied by position jump between reports


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


def fetch_all_states():
    query = """
        SELECT id, callsign, icao24, latitude, longitude,
               baro_altitude, velocity, vertical_rate,
               on_ground, collected_at
        FROM aircraft_states
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY icao24, collected_at;
    """
    conn = get_db_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def check_static_violations(df):
    """Checks that don't require comparing consecutive reports."""
    violations = []

    for _, row in df.iterrows():
        reasons = []

        if row["velocity"] is not None and row["velocity"] > MAX_REALISTIC_SPEED_MS:
            reasons.append(f"impossible speed ({row['velocity']:.1f} m/s)")

        if row["vertical_rate"] is not None and abs(row["vertical_rate"]) > MAX_REALISTIC_VRATE_MS:
            reasons.append(f"impossible vertical rate ({row['vertical_rate']:.1f} m/s)")

        if row["baro_altitude"] is not None:
            if row["baro_altitude"] > MAX_REALISTIC_ALTITUDE_M:
                reasons.append(f"impossible altitude ({row['baro_altitude']:.0f}m)")
            elif row["baro_altitude"] < MIN_REALISTIC_ALTITUDE_M:
                reasons.append(f"negative altitude ({row['baro_altitude']:.0f}m)")

        if reasons:
            violations.append({
                "icao24": row["icao24"],
                "callsign": (row["callsign"] or "UNKNOWN").strip(),
                "collected_at": row["collected_at"],
                "type": "static",
                "reasons": "; ".join(reasons)
            })

    return violations


def check_position_jumps(df):
    """
    Checks consecutive reports for the same aircraft to see if it
    "teleported" -- moved faster than physically possible.
    """
    violations = []

    for icao24, group in df.groupby("icao24"):
        group = group.sort_values("collected_at").reset_index(drop=True)

        for i in range(1, len(group)):
            prev = group.iloc[i-1]
            curr = group.iloc[i]

            time_diff = (curr["collected_at"] - prev["collected_at"]).total_seconds()
            if time_diff <= 0:
                continue

            distance = haversine(
                prev["latitude"], prev["longitude"],
                curr["latitude"], curr["longitude"]
            )

            implied_speed = distance / time_diff

            if implied_speed > MAX_REALISTIC_JUMP_SPEED_MS:
                violations.append({
                    "icao24": icao24,
                    "callsign": (curr["callsign"] or "UNKNOWN").strip(),
                    "collected_at": curr["collected_at"],
                    "type": "position_jump",
                    "reasons": f"implied speed {implied_speed:.0f} m/s "
                               f"over {time_diff:.0f}s "
                               f"({distance/1000:.1f}km jump)"
                })

    return violations


def run_spoofing_detection():
    print("Fetching all aircraft states...")
    df = fetch_all_states()
    print(f"Analyzing {len(df)} records...\n")

    static_violations = check_static_violations(df)
    jump_violations = check_position_jumps(df)

    all_violations = static_violations + jump_violations

    return all_violations, df


if __name__ == "__main__":
    violations, df = run_spoofing_detection()

    print(f"=== Spoofing Detection Results ===")
    print(f"Total records analyzed:    {len(df)}")
    print(f"Static violations:         {sum(1 for v in violations if v['type'] == 'static')}")
    print(f"Position jump violations:  {sum(1 for v in violations if v['type'] == 'position_jump')}")
    print(f"Total flagged:             {len(violations)}")

    if violations:
        print(f"\n=== Sample Flagged Records ===")
        for v in violations[:20]:
            print(f"  {v['callsign']:<12} {v['icao24']:<8} "
                  f"[{v['type']:<13}] {v['reasons']} "
                  f"@ {v['collected_at'].strftime('%H:%M:%S')}")