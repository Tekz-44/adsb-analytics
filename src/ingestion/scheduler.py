"""
Scheduler.
Runs the data collector every 60 seconds automatically.
"""

import schedule
import time
import logging
import os
from dotenv import load_dotenv

from opensky_client import get_aircraft_states
from db_inserter import insert_aircraft_states

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


def collect_and_store():
    """Single collection cycle — fetch from OpenSky and insert into DB."""
    logger.info("Starting collection cycle...")
    username = os.getenv("OPENSKY_USERNAME")
    password = os.getenv("OPENSKY_PASSWORD")

    states = get_aircraft_states(username, password)
    inserted = insert_aircraft_states(states)
    logger.info(f"Cycle complete. {inserted} records inserted.")


if __name__ == "__main__":
    logger.info("Scheduler started. Collecting every 60 seconds.")
    
    # Run once immediately on startup
    collect_and_store()

    # Then every 60 seconds
    schedule.every(60).seconds.do(collect_and_store)

    while True:
        schedule.run_pending()
        time.sleep(1)