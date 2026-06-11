"""
Map visualizer.
Generates an interactive HTML map of flight paths around KDTW.
"""

import folium
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# KDTW coordinates
KDTW_LAT = 42.2124
KDTW_LON = -83.3534


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "adsb"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def get_flight_paths(min_points=5):
    """Get all flight paths with enough data points to be meaningful."""
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
        callsign = row[0].strip()
        if callsign not in paths:
            paths[callsign] = []
        paths[callsign].append((row[1], row[2], row[3], row[4]))

    return {k: v for k, v in paths.items() if len(v) >= min_points}


def altitude_to_color(altitude):
    """Map altitude to a color — blue=low, green=mid, red=high."""
    if altitude is None:
        return "gray"
    if altitude < 1000:
        return "#00bfff"   # light blue — low/approach
    elif altitude < 5000:
        return "#00cc44"   # green — mid altitude
    elif altitude < 10000:
        return "#ffaa00"   # orange — high
    else:
        return "#ff3333"   # red — cruising


def generate_map(output_path="docs/flight_map.html"):
    """Generate an interactive flight path map centered on KDTW."""
    paths = get_flight_paths()
    print(f"Plotting {len(paths)} aircraft trajectories...")

    # Create map centered on KDTW
    m = folium.Map(
        location=[KDTW_LAT, KDTW_LON],
        zoom_start=9,
        tiles="CartoDB dark_matter"
    )

    # Add KDTW airport marker
    folium.Marker(
        location=[KDTW_LAT, KDTW_LON],
        popup="KDTW — Detroit Metro Airport",
        icon=folium.Icon(color="white", icon="plane", prefix="fa")
    ).add_to(m)

    # Plot each flight path
    colors = [
        "#00bfff", "#00cc44", "#ffaa00", "#ff3333",
        "#cc00ff", "#ff69b4", "#00ffcc", "#ffff00"
    ]

    for i, (callsign, points) in enumerate(paths.items()):
        coords = [(p[0], p[1]) for p in points]
        color = colors[i % len(colors)]

        # Draw the path
        folium.PolyLine(
            coords,
            color=color,
            weight=2,
            opacity=0.8,
            tooltip=callsign
        ).add_to(m)

        # Mark start and end points
        folium.CircleMarker(
            location=coords[0],
            radius=4,
            color=color,
            fill=True,
            popup=f"{callsign} — start"
        ).add_to(m)

        folium.CircleMarker(
            location=coords[-1],
            radius=4,
            color=color,
            fill=True,
            popup=f"{callsign} — end"
        ).add_to(m)

    # Save the map
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    m.save(output_path)
    print(f"Map saved to {output_path}")
    return output_path


if __name__ == "__main__":
    path = generate_map()
    print(f"\nOpen this file in your browser to see the map:")
    print(f"  {os.path.abspath(path)}")