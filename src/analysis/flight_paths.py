"""
Flight path analysis.
Reconstructs individual aircraft trajectories from collected states.
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


def get_flight_path(callsign: str):
    """
    Get the full trajectory of a specific aircraft by callsign.
    Returns a list of (lat, lon, altitude, time) tuples.
    """
    query = """
        SELECT latitude, longitude, baro_altitude, collected_at
        FROM aircraft_states
        WHERE callsign = %s
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY collected_at;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (callsign,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_flight_paths():
    """
    Get trajectories for all aircraft with enough data points.
    Returns a dict of callsign -> list of (lat, lon, altitude, time).
    """
    query = """
        SELECT callsign, latitude, longitude, baro_altitude, collected_at
        FROM aircraft_states
        WHERE callsign IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        ORDER BY callsign, collected_at;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    paths = {}
    for row in rows:
        callsign = row[0]
        if callsign not in paths:
            paths[callsign] = []
        paths[callsign].append({
            "lat": row[1],
            "lon": row[2],
            "altitude": row[3],
            "time": row[4]
        })

    return paths


def get_top_paths(min_points=10, limit=10):
    """
    Get aircraft with the most data points — best trajectories to visualize.
    """
    query = """
        SELECT callsign, COUNT(*) as points
        FROM aircraft_states
        WHERE callsign IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        GROUP BY callsign
        HAVING COUNT(*) >= %s
        ORDER BY points DESC
        LIMIT %s;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, (min_points, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    print("\n=== Aircraft with Best Flight Path Data ===")
    top = get_top_paths()
    for row in top:
        print(f"  {row[0]:<12} {row[1]} data points")

    if top:
        # Show detailed path for the most tracked aircraft
        best = top[0][0]
        print(f"\n=== Flight Path for {best} ===")
        path = get_flight_path(best)
        print(f"  Total points: {len(path)}")
        print(f"  First seen: {path[0][3]}")
        print(f"  Last seen:  {path[-1][3]}")
        print(f"  Alt range:  {min(p[2] for p in path if p[2]):.0f}m "
              f"— {max(p[2] for p in path if p[2]):.0f}m")
        print(f"\n  Sample points (every 10th):")
        for p in path[::10]:
            print(f"    {p[3].strftime('%H:%M:%S')} | "
                  f"lat={p[0]:.4f} lon={p[1]:.4f} | "
                  f"alt={p[2]:.0f}m")