-- ============================================================================
-- schema.sql
-- EV Charging Station Utilization & Demand Analytics
-- Target: PostgreSQL (also SQLite-compatible with minor type substitutions)
-- ============================================================================

DROP TABLE IF EXISTS charging_sessions;
DROP TABLE IF EXISTS stations;

CREATE TABLE stations (
    station_id           VARCHAR(10) PRIMARY KEY,
    station_name         VARCHAR(100) NOT NULL,
    city                 VARCHAR(50) NOT NULL,
    area                 VARCHAR(50) NOT NULL,
    latitude             DECIMAL(9,5),
    longitude            DECIMAL(9,5),
    charger_type         VARCHAR(30) NOT NULL,
    number_of_chargers   INT NOT NULL CHECK (number_of_chargers > 0)
);

CREATE TABLE charging_sessions (
    session_id                 VARCHAR(15) PRIMARY KEY,
    station_id                 VARCHAR(10) NOT NULL REFERENCES stations(station_id),
    session_date                DATE NOT NULL,
    start_time                  TIMESTAMP NOT NULL,
    end_time                    TIMESTAMP,
    vehicle_type                VARCHAR(30),
    energy_consumed_kwh          DECIMAL(8,2) CHECK (energy_consumed_kwh >= 0),
    charging_duration_minutes    DECIMAL(8,2) CHECK (charging_duration_minutes >= 0),
    waiting_time_minutes         DECIMAL(8,2) CHECK (waiting_time_minutes >= 0),
    charging_cost                DECIMAL(10,2),
    revenue                      DECIMAL(10,2),
    session_status               VARCHAR(15),
    day_of_week                  SMALLINT,   -- 0 = Monday ... 6 = Sunday
    hour                         SMALLINT,
    month                        SMALLINT,
    peak_hour                    BOOLEAN,
    weather_condition            VARCHAR(20)
);

CREATE INDEX idx_sessions_station ON charging_sessions(station_id);
CREATE INDEX idx_sessions_date ON charging_sessions(session_date);
CREATE INDEX idx_sessions_hour ON charging_sessions(hour);

-- Load data (psql example):
-- \copy stations FROM 'data/raw/station_master.csv' WITH (FORMAT csv, HEADER true);
-- \copy charging_sessions FROM 'data/processed/ev_charging_cleaned.csv' WITH (FORMAT csv, HEADER true);
