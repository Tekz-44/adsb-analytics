"""
Database inserter.
Takes aircraft states from OpenSky and saves them to PostgreSQL.
"""

import psycopg2
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Create and return a database connection."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "adsb"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )


def insert_aircraft_states(states: list) -> int:
    """
    Insert a list of aircraft states into the database.
    Returns the number of rows inserted.
    """
    if not states:
        logger.warning("No states to insert.")
        return 0

    insert_query = """
        INSERT INTO aircraft_states (
            icao24, callsign, origin_country,
            time_position, last_contact,
            longitude, latitude, baro_altitude,
            on_ground, velocity, true_track,
            vertical_rate, geo_altitude, squawk,
            position
        ) VALUES (
            %(icao24)s, %(callsign)s, %(origin_country)s,
            %(time_position)s, %(last_contact)s,
            %(longitude)s, %(latitude)s, %(baro_altitude)s,
            %(on_ground)s, %(velocity)s, %(true_track)s,
            %(vertical_rate)s, %(geo_altitude)s, %(squawk)s,
            CASE
                WHEN %(longitude)s IS NOT NULL AND %(latitude)s IS NOT NULL
                THEN ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)
                ELSE NULL
            END
        )
    """

    conn = None
    inserted = 0

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        for state in states:
            cur.execute(insert_query, state)
            inserted += 1

        conn.commit()
        logger.info(f"Inserted {inserted} aircraft states into database.")

    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()

    finally:
        if conn:
            conn.close()

    return inserted


if __name__ == "__main__":
    from opensky_client import get_aircraft_states

    username = os.getenv("OPENSKY_USERNAME")
    password = os.getenv("OPENSKY_PASSWORD")

    states = get_aircraft_states(username, password)
    inserted = insert_aircraft_states(states)
    print(f"Successfully inserted {inserted} records into the database.")