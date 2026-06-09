"""
OpenSky Network API client.
Pulls live aircraft state vectors within a bounding box around KDTW.
"""

import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# KDTW bounding box (lat/lon area around Detroit Metro Airport)
KDTW_BBOX = {
    "lamin": 41.8,   # min latitude
    "lomin": -84.0,  # min longitude
    "lamax": 42.5,   # max latitude
    "lomax": -83.0   # max longitude
}

OPENSKY_BASE_URL = "https://opensky-network.org/api"


def get_aircraft_states(username: str, password: str) -> list:
    """
    Fetch live aircraft states around KDTW from OpenSky Network.
    Returns a list of aircraft state dictionaries.
    """
    url = f"{OPENSKY_BASE_URL}/states/all"
    
    params = {
        "lamin": KDTW_BBOX["lamin"],
        "lomin": KDTW_BBOX["lomin"],
        "lamax": KDTW_BBOX["lamax"],
        "lomax": KDTW_BBOX["lomax"]
    }

    try:
        logger.info("Fetching aircraft states from OpenSky...")
        response = requests.get(
            url,
            params=params,
            auth=(username, password),
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if not data or "states" not in data or data["states"] is None:
            logger.warning("No aircraft states returned.")
            return []

        states = []
        for s in data["states"]:
            states.append({
                "icao24":         s[0],
                "callsign":       s[1].strip() if s[1] else None,
                "origin_country": s[2],
                "time_position":  s[3],
                "last_contact":   s[4],
                "longitude":      s[5],
                "latitude":       s[6],
                "baro_altitude":  s[7],
                "on_ground":      s[8],
                "velocity":       s[9],
                "true_track":     s[10],
                "vertical_rate":  s[11],
                "geo_altitude":   s[13],
                "squawk":         s[14],
            })

        logger.info(f"Got {len(states)} aircraft around KDTW.")
        return states

    except requests.exceptions.RequestException as e:
        logger.error(f"OpenSky API error: {e}")
        return []


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    username = os.getenv("OPENSKY_USERNAME")
    password = os.getenv("OPENSKY_PASSWORD")

    states = get_aircraft_states(username, password)

    for aircraft in states[:5]:
        print(f"{aircraft['callsign']} | {aircraft['icao24']} | "
              f"Alt: {aircraft['baro_altitude']}m | "
              f"Speed: {aircraft['velocity']}m/s | "
              f"On ground: {aircraft['on_ground']}")