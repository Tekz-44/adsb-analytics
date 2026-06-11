"""
Separation metrics.
Calculates how close aircraft are getting to each other around KDTW.
Nav Canada uses separation standards to keep aircraft safe —
this module measures whether those standards are being maintained.

ICAO standard separation minimums:
- Horizontal: 5 nautical miles (9,260m)
- Vertical: 1000 feet (305m)
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# ICAO separation minimums
MIN_HORIZONTAL_SEP_M = 9260   # 5 nautical miles in meters
MIN_VERTICAL_SEP_M = 305      # 1000 feet in meters


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "adsb"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def get_closest_approaches(limit=20):
    """
    Find pairs of aircraft that were closest to each other
    at the same point in time.
    Uses PostGIS ST_Distance for accurate geographic distance.
    """
    query = """
        SELECT
            a.callsign AS aircraft_1,
            b.callsign AS aircraft_2,
            ROUND(ST_Distance(
                ST_Transform(a.position::geometry, 3857),
                ST_Transform(b.position::geometry, 3857)
            )::numeric, 2) AS horizontal_distance_m,
            ROUND(ABS(a.baro_altitude - b.baro_altitude)::numeric, 2)
                AS vertical_distance_m,
            a.collected_at
        FROM aircraft_states a
        JOIN aircraft_states b
            ON a.collected_at = b.collected_at
            AND a.icao24 < b.icao24
            AND a.position IS NOT NULL
            AND b.position IS NOT NULL
            AND a.baro_altitude IS NOT NULL
            AND b.baro_altitude IS NOT NULL
            AND a.on_ground = FALSE
            AND b.on_ground = FALSE
        ORDER BY horizontal_distance_m ASC
        LIMIT %s;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_separation_violations():
    """
    Find instances where two aircraft were below ICAO minimums
    on BOTH horizontal AND vertical separation simultaneously.
    These are the most safety-critical events in the dataset.
    """
    query = """
        SELECT
            a.callsign AS aircraft_1,
            b.callsign AS aircraft_2,
            ROUND(ST_Distance(
                ST_Transform(a.position::geometry, 3857),
                ST_Transform(b.position::geometry, 3857)
            )::numeric, 2) AS horizontal_m,
            ROUND(ABS(a.baro_altitude - b.baro_altitude)::numeric, 2)
                AS vertical_m,
            a.collected_at
        FROM aircraft_states a
        JOIN aircraft_states b
            ON a.collected_at = b.collected_at
            AND a.icao24 < b.icao24
            AND a.position IS NOT NULL
            AND b.position IS NOT NULL
            AND a.baro_altitude IS NOT NULL
            AND b.baro_altitude IS NOT NULL
            AND a.on_ground = FALSE
            AND b.on_ground = FALSE
        WHERE
            ST_Distance(
                ST_Transform(a.position::geometry, 3857),
                ST_Transform(b.position::geometry, 3857)
            ) < %(horiz)s
            AND ABS(a.baro_altitude - b.baro_altitude) < %(vert)s
        ORDER BY horizontal_m ASC;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, {
        "horiz": MIN_HORIZONTAL_SEP_M,
        "vert": MIN_VERTICAL_SEP_M
    })
    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    print("\n=== Closest Aircraft Approaches Around KDTW ===")
    print(f"{'Aircraft 1':<12} {'Aircraft 2':<12} "
          f"{'Horiz (m)':<12} {'Vert (m)':<12} Time")
    print("-" * 70)

    for row in get_closest_approaches():
        print(f"{row[0]:<12} {row[1]:<12} "
              f"{row[2]:<12} {row[3]:<12} "
              f"{row[4].strftime('%H:%M:%S')}")

    print(f"\n=== Separation Violations (below ICAO minimums) ===")
    print(f"Horizontal minimum: {MIN_HORIZONTAL_SEP_M}m (5nm)")
    print(f"Vertical minimum:   {MIN_VERTICAL_SEP_M}m (1000ft)")
    print("-" * 70)

    violations = get_separation_violations()
    if violations:
        for row in violations:
            c1 = (row[0] or "UNKNOWN").strip()
            c2 = (row[1] or "UNKNOWN").strip()
            print(f"{c1:<12} {c2:<12} "
                  f"horiz={row[2]}m  vert={row[3]}m  "
                  f"{row[4].strftime('%H:%M:%S')}")
    else:
        print("No violations found in current dataset.")