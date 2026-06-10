"""
Basic statistics and analysis queries.
Week 2 — understanding our KDTW dataset.
"""

import psycopg2
import os
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


def most_frequent_aircraft(limit=10):
    """Which aircraft appear most often around KDTW?"""
    query = """
        SELECT callsign, icao24, COUNT(*) as appearances
        FROM aircraft_states
        WHERE callsign IS NOT NULL
        GROUP BY callsign, icao24
        ORDER BY appearances DESC
        LIMIT %s;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def busiest_hours():
    """What hours of the day have the most aircraft around KDTW?"""
    query = """
        SELECT EXTRACT(HOUR FROM collected_at) AS hour,
               COUNT(DISTINCT icao24) AS unique_aircraft
        FROM aircraft_states
        GROUP BY hour
        ORDER BY hour;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows


def air_vs_ground():
    """Ratio of airborne vs on-ground aircraft over time."""
    query = """
        SELECT on_ground,
               COUNT(*) as count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
        FROM aircraft_states
        GROUP BY on_ground;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows


def altitude_distribution():
    """Average, min, and max altitude of aircraft around KDTW."""
    query = """
        SELECT
            ROUND(AVG(baro_altitude)::numeric, 2) AS avg_altitude,
            ROUND(MIN(baro_altitude)::numeric, 2) AS min_altitude,
            ROUND(MAX(baro_altitude)::numeric, 2) AS max_altitude
        FROM aircraft_states
        WHERE baro_altitude IS NOT NULL AND on_ground = FALSE;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query)
    row = cur.fetchone()
    conn.close()
    return row


if __name__ == "__main__":
    print("\n=== Most Frequent Aircraft Around KDTW ===")
    for row in most_frequent_aircraft():
        print(f"  {row[0]:<12} {row[1]:<10} {row[2]} appearances")

    print("\n=== Aircraft Count by Hour of Day ===")
    for row in busiest_hours():
        bar = "█" * (row[1] // 5)
        print(f"  {int(row[0]):02d}:00  {bar} {row[1]}")

    print("\n=== Airborne vs On Ground ===")
    for row in air_vs_ground():
        status = "On ground" if row[0] else "Airborne "
        print(f"  {status}: {row[1]} records ({row[2]}%)")

    print("\n=== Altitude Statistics (airborne only) ===")
    row = altitude_distribution()
    print(f"  Average: {row[0]}m")
    print(f"  Minimum: {row[1]}m")
    print(f"  Maximum: {row[2]}m")