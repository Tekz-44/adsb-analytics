-- ADS-B Analytics Platform — Database Schema
-- Run with: psql adsb -f sql/schema.sql

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS aircraft_states (
    id SERIAL PRIMARY KEY,
    icao24 VARCHAR(10) NOT NULL,
    callsign VARCHAR(20),
    origin_country VARCHAR(100),
    time_position BIGINT,
    last_contact BIGINT,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    baro_altitude DOUBLE PRECISION,
    on_ground BOOLEAN,
    velocity DOUBLE PRECISION,
    true_track DOUBLE PRECISION,
    vertical_rate DOUBLE PRECISION,
    geo_altitude DOUBLE PRECISION,
    squawk VARCHAR(10),
    position GEOMETRY(Point, 4326),
    collected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aircraft_icao24 ON aircraft_states(icao24);
CREATE INDEX IF NOT EXISTS idx_aircraft_time ON aircraft_states(collected_at);
CREATE INDEX IF NOT EXISTS idx_aircraft_position ON aircraft_states USING GIST(position);