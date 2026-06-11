"""
Routing efficiency analysis.
Measures how efficiently aircraft are flying around KDTW.
Compares actual distance flown vs straight-line distance.
An efficiency of 1.0 = perfect straight line.
Higher = more deviation from optimal path.
"""

import psycopg2
import os
import math
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
    """
    Calculate distance in meters between two GPS coordinates.
    Uses the Haversine formula.
    """
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_routing_efficiency(min_points=10):
    """
    For each aircraft with enough data points, calculate:
    - Total distance actually flown
    - Straight-line distance from first to last point
    - Efficiency ratio (straight-line / actual)
    """
    query = """
        SELECT callsign, latitude, longitude, collected_at
        FROM aircraft_states
        WHERE callsign IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND on_ground = FALSE
        ORDER BY callsign, collected_at;
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    # Group by callsign
    paths = {}
    for row in rows:
        callsign = row[0].strip()
        if callsign not in paths:
            paths[callsign] = []
        paths[callsign].append((row[1], row[2], row[3]))

    results = []
    for callsign, points in paths.items():
        if len(points) < min_points:
            continue

        # Calculate total distance flown (sum of all segments)
        total_distance = 0
        for i in range(1, len(points)):
            total_distance += haversine(
                points[i-1][0], points[i-1][1],
                points[i][0],   points[i][1]
            )

        # Calculate straight-line distance (first to last point)
        straight_line = haversine(
            points[0][0],  points[0][1],
            points[-1][0], points[-1][1]
        )

        if total_distance == 0 or straight_line == 0:
            continue

        efficiency = straight_line / total_distance

        results.append({
            "callsign":        callsign,
            "points":          len(points),
            "total_km":        round(total_distance / 1000, 2),
            "straight_km":     round(straight_line / 1000, 2),
            "efficiency":      round(efficiency, 3),
            "first_seen":      points[0][2],
            "last_seen":       points[-1][2],
        })

    return sorted(results, key=lambda x: x["efficiency"], reverse=True)


if __name__ == "__main__":
    results = get_routing_efficiency()

    print(f"\n=== Routing Efficiency Around KDTW ===")
    print(f"{'Callsign':<12} {'Points':<8} {'Actual km':<12} "
          f"{'Straight km':<14} {'Efficiency':<12}")
    print("-" * 60)

    for r in results:
        bar = "█" * int(r["efficiency"] * 20)
        print(f"{r['callsign']:<12} {r['points']:<8} "
              f"{r['total_km']:<12} {r['straight_km']:<14} "
              f"{r['efficiency']:<8} {bar}")

    if results:
        avg = round(sum(r["efficiency"] for r in results) / len(results), 3)
        most = max(results, key=lambda x: x["efficiency"])
        least = min(results, key=lambda x: x["efficiency"])

        print(f"\n=== Summary ===")
        print(f"  Aircraft analyzed:   {len(results)}")
        print(f"  Average efficiency:  {avg}")
        print(f"  Most efficient:      {most['callsign']} ({most['efficiency']})")
        print(f"  Least efficient:     {least['callsign']} ({least['efficiency']})")