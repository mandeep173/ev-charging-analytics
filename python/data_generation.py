"""
data_generation.py
===================
Generates a realistic SYNTHETIC EV charging session dataset for
"EV Charging Station Utilization & Demand Analytics".

IMPORTANT: This is synthetic data, not real-world data. It is built with
deliberate statistical relationships (peak-hour demand, utilization-driven
waiting times, charger/vehicle-type effects on duration, station-level
demand tiers, etc.) so that downstream analysis is meaningful, but the
absolute numbers do not represent any real company or city.

Real public EV-charging session datasets (e.g. individual charging-station
utilization logs with per-session timestamps, energy, and revenue) are not
freely available at the 50k-100k row granularity this project needs without
usage restrictions, so a synthetic generator is used instead and clearly
labeled as such throughout the project (README, report, and a
`is_synthetic` marker column).

Run:
    python python/data_generation.py
Produces:
    data/raw/ev_charging_raw.csv
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RANDOM_SEED = 42
N_SESSIONS = 85000
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 12, 31)

rng = np.random.default_rng(RANDOM_SEED)


# ---------------------------------------------------------------------------
# 1. STATION MASTER DATA
# ---------------------------------------------------------------------------
def build_station_master():
    """
    Builds a fixed set of charging stations across multiple cities/areas.
    Each station is assigned a 'demand_tier' which drives how often it is
    sampled for sessions later -- this is what creates realistic variation
    between busy, moderate, and underutilized stations.
    """
    cities_areas = {
        "Delhi": ["Connaught Place", "Dwarka", "Rohini", "Saket", "Karol Bagh"],
        "Mumbai": ["Andheri", "Bandra", "Powai", "Thane", "Borivali"],
        "Bengaluru": ["Whitefield", "Koramangala", "Indiranagar", "Electronic City", "Jayanagar"],
        "Pune": ["Hinjewadi", "Kothrud", "Viman Nagar", "Baner"],
        "Hyderabad": ["Hitech City", "Gachibowli", "Kukatpally"],
    }

    # Approximate lat/lon centers per city, jittered per area
    city_coords = {
        "Delhi": (28.6139, 77.2090),
        "Mumbai": (19.0760, 72.8777),
        "Bengaluru": (12.9716, 77.5946),
        "Pune": (18.5204, 73.8567),
        "Hyderabad": (17.3850, 78.4867),
    }

    charger_types = ["AC Slow (3.3kW)", "AC Fast (7.4kW)", "DC Fast (50kW)", "DC Ultra-Fast (150kW)"]
    # Weight charger type mix realistically -- most stations are AC Fast or DC Fast
    charger_type_weights = [0.15, 0.40, 0.35, 0.10]

    stations = []
    station_id = 1000
    for city, areas in cities_areas.items():
        base_lat, base_lon = city_coords[city]
        for area in areas:
            # 2-4 stations per area
            n_stations_here = rng.integers(2, 5)
            for _ in range(n_stations_here):
                station_id += 1
                charger_type = rng.choice(charger_types, p=charger_type_weights)
                # Number of chargers correlates loosely with charger type (fast chargers -> fewer bays, more $$ per bay)
                if charger_type == "AC Slow (3.3kW)":
                    n_chargers = rng.integers(4, 10)
                elif charger_type == "AC Fast (7.4kW)":
                    n_chargers = rng.integers(3, 8)
                elif charger_type == "DC Fast (50kW)":
                    n_chargers = rng.integers(2, 6)
                else:
                    n_chargers = rng.integers(1, 4)

                # demand_tier drives sampling probability later: creates busy vs quiet stations
                demand_tier = rng.choice(
                    ["very_high", "high", "moderate", "low"],
                    p=[0.12, 0.28, 0.40, 0.20],
                )

                stations.append({
                    "station_id": f"ST{station_id}",
                    "station_name": f"{area} EV Hub {station_id}",
                    "city": city,
                    "area": area,
                    "latitude": round(base_lat + rng.normal(0, 0.06), 5),
                    "longitude": round(base_lon + rng.normal(0, 0.06), 5),
                    "charger_type": charger_type,
                    "number_of_chargers": int(n_chargers),
                    "demand_tier": demand_tier,
                })

    return pd.DataFrame(stations)


DEMAND_TIER_WEIGHT = {"very_high": 6.0, "high": 3.0, "moderate": 1.5, "low": 0.6}


# ---------------------------------------------------------------------------
# 2. TIME-OF-DAY / SEASONAL DEMAND SHAPE
# ---------------------------------------------------------------------------
def hourly_demand_weight(hour):
    """
    Returns a relative demand weight for a given hour of day.
    Two peaks: morning commute charging (8-10) and evening (18-21),
    a smaller overnight base load (residential slow charging).
    """
    weights = {
        0: 1.5, 1: 1.0, 2: 0.7, 3: 0.5, 4: 0.5, 5: 0.7,
        6: 1.2, 7: 2.0, 8: 3.2, 9: 3.6, 10: 2.8, 11: 2.2,
        12: 2.0, 13: 2.0, 14: 2.1, 15: 2.3, 16: 2.6, 17: 3.2,
        18: 4.0, 19: 4.3, 20: 3.8, 21: 2.9, 22: 2.0, 23: 1.7,
    }
    return weights[hour]


def monthly_demand_weight(month):
    """
    Mild seasonality: slightly lower in peak summer heat (Apr-Jun, battery
    range anxiety + AC load) and a festive-season dip in Oct/Nov, with
    growth trend across the year as EV adoption grows.
    """
    base = {1: 0.85, 2: 0.88, 3: 0.95, 4: 0.90, 5: 0.88, 6: 0.92,
            7: 1.00, 8: 1.02, 9: 1.05, 10: 0.95, 11: 1.05, 12: 1.15}
    return base[month]


def weekday_weight(dow):
    """0=Monday ... 6=Sunday. Slightly lower demand on weekends for commuter-heavy stations."""
    return {0: 1.05, 1: 1.05, 2: 1.05, 3: 1.05, 4: 1.1, 5: 0.85, 6: 0.75}[dow]


# ---------------------------------------------------------------------------
# 3. SESSION GENERATION
# ---------------------------------------------------------------------------
VEHICLE_TYPES = ["2-Wheeler", "3-Wheeler", "Car - Hatchback/Sedan", "Car - SUV", "Light Commercial"]
VEHICLE_WEIGHTS = [0.30, 0.15, 0.30, 0.18, 0.07]

# Typical battery/charging behavior per vehicle type (kWh needed per session, base minutes per kWh)
VEHICLE_PROFILE = {
    "2-Wheeler": {"kwh_mean": 2.2, "kwh_sd": 0.6},
    "3-Wheeler": {"kwh_mean": 4.5, "kwh_sd": 1.0},
    "Car - Hatchback/Sedan": {"kwh_mean": 18.0, "kwh_sd": 5.0},
    "Car - SUV": {"kwh_mean": 28.0, "kwh_sd": 7.0},
    "Light Commercial": {"kwh_mean": 35.0, "kwh_sd": 9.0},
}

# Charging speed in kW actually delivered (a bit below rated, real-world derating)
CHARGER_KW = {
    "AC Slow (3.3kW)": 2.8,
    "AC Fast (7.4kW)": 6.3,
    "DC Fast (50kW)": 38.0,
    "DC Ultra-Fast (150kW)": 95.0,
}

WEATHER_CONDITIONS = ["Clear", "Cloudy", "Rain", "Hot", "Foggy"]
WEATHER_WEIGHTS = [0.45, 0.20, 0.15, 0.15, 0.05]

COST_PER_KWH_BY_CHARGER = {
    "AC Slow (3.3kW)": 8.5,
    "AC Fast (7.4kW)": 10.5,
    "DC Fast (50kW)": 15.0,
    "DC Ultra-Fast (150kW)": 19.5,
}


def generate_sessions(stations_df, n_sessions=N_SESSIONS):
    total_days = (END_DATE - START_DATE).days + 1

    # Sampling weight per station combines demand tier with number of chargers
    # (more bays -> naturally more sessions can be served there)
    station_weights = (
        stations_df["demand_tier"].map(DEMAND_TIER_WEIGHT).to_numpy()
        * (0.6 + 0.4 * stations_df["number_of_chargers"].to_numpy() / stations_df["number_of_chargers"].max())
    )
    station_probs = station_weights / station_weights.sum()

    station_idx = rng.choice(len(stations_df), size=n_sessions, p=station_probs)
    chosen_stations = stations_df.iloc[station_idx].reset_index(drop=True)

    # Sample day using a weight per calendar day that combines month seasonality and
    # weekday/weekend effect, so demand actually varies by day-of-week and month
    # (rather than being uniform and only varying by hour-of-day).
    all_days = pd.date_range(START_DATE, END_DATE, freq="D")
    day_weight_arr = np.array([
        monthly_demand_weight(d.month) * weekday_weight(d.dayofweek) for d in all_days
    ])
    day_probs = day_weight_arr / day_weight_arr.sum()
    day_idx = rng.choice(total_days, size=n_sessions, p=day_probs)
    dates = all_days[day_idx]
    months = dates.month.to_numpy()
    dows = dates.dayofweek.to_numpy()

    # Sample hour using demand-weighted distribution, then adjust slightly by weekday
    hour_weights = np.array([hourly_demand_weight(h) for h in range(24)])
    hour_probs = hour_weights / hour_weights.sum()
    hours = rng.choice(24, size=n_sessions, p=hour_probs)

    minutes_start = rng.integers(0, 60, size=n_sessions)

    vehicle_types = rng.choice(VEHICLE_TYPES, size=n_sessions, p=VEHICLE_WEIGHTS)
    weather = rng.choice(WEATHER_CONDITIONS, size=n_sessions, p=WEATHER_WEIGHTS)

    charger_types = chosen_stations["charger_type"].to_numpy()
    n_chargers_arr = chosen_stations["number_of_chargers"].to_numpy()
    demand_tier_arr = chosen_stations["demand_tier"].to_numpy()

    # --- Energy consumed: driven by vehicle profile, with some noise ---
    kwh_mean = np.array([VEHICLE_PROFILE[v]["kwh_mean"] for v in vehicle_types])
    kwh_sd = np.array([VEHICLE_PROFILE[v]["kwh_sd"] for v in vehicle_types])
    energy_consumed = np.clip(rng.normal(kwh_mean, kwh_sd), 0.3, None)

    # --- Charging duration: energy / effective charger power, plus overhead & noise ---
    charger_kw = np.array([CHARGER_KW[c] for c in charger_types])
    base_minutes = (energy_consumed / charger_kw) * 60.0
    overhead_minutes = rng.normal(6, 2, size=n_sessions).clip(0, None)  # plug-in/session-start overhead
    charging_duration = np.clip(base_minutes + overhead_minutes + rng.normal(0, 4, size=n_sessions), 3, None)

    # --- Utilization proxy per station-hour: busier tiers + peak hours -> more concurrent demand ---
    tier_pressure = np.array([DEMAND_TIER_WEIGHT[t] for t in demand_tier_arr])
    hour_pressure = np.array([hourly_demand_weight(h) for h in hours])
    # normalize pressures roughly to 0-1 range for waiting-time model
    pressure_score = (tier_pressure / tier_pressure.max()) * (hour_pressure / hour_pressure.max())
    # fewer chargers relative to pressure -> longer waits
    capacity_factor = pressure_score / np.sqrt(n_chargers_arr)

    waiting_time = np.clip(
        rng.gamma(shape=1.6, scale=4.0, size=n_sessions) * (1 + 3.5 * capacity_factor),
        0, None,
    )

    # --- Cost & revenue ---
    cost_per_kwh = np.array([COST_PER_KWH_BY_CHARGER[c] for c in charger_types])
    # small random discounts/surcharges
    price_noise = rng.normal(1.0, 0.05, size=n_sessions)
    charging_cost = energy_consumed * cost_per_kwh * price_noise
    revenue = charging_cost  # in this business model, session cost IS the revenue line (no separate subsidy)

    # --- Session status: mostly completed, some cancelled/failed ---
    status_probs = [0.90, 0.05, 0.05]
    session_status = rng.choice(["Completed", "Cancelled", "Failed"], size=n_sessions, p=status_probs)

    # start/end timestamps
    start_dt = dates + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes_start, unit="m")
    end_dt = start_dt + pd.to_timedelta(charging_duration, unit="m")

    peak_hour_flag = np.isin(hours, [8, 9, 18, 19, 20])

    df = pd.DataFrame({
        "session_id": [f"SESS{100000+i}" for i in range(n_sessions)],
        "date": dates.date,
        "start_time": start_dt,
        "end_time": end_dt,
        "station_id": chosen_stations["station_id"].to_numpy(),
        "station_name": chosen_stations["station_name"].to_numpy(),
        "city": chosen_stations["city"].to_numpy(),
        "area": chosen_stations["area"].to_numpy(),
        "latitude": chosen_stations["latitude"].to_numpy(),
        "longitude": chosen_stations["longitude"].to_numpy(),
        "charger_type": charger_types,
        "number_of_chargers": n_chargers_arr,
        "vehicle_type": vehicle_types,
        "energy_consumed_kwh": np.round(energy_consumed, 2),
        "charging_duration_minutes": np.round(charging_duration, 1),
        "waiting_time_minutes": np.round(waiting_time, 1),
        "charging_cost": np.round(charging_cost, 2),
        "revenue": np.round(revenue, 2),
        "session_status": session_status,
        "day_of_week": dows,
        "hour": hours,
        "month": months,
        "peak_hour": peak_hour_flag,
        "weather_condition": weather,
        "is_synthetic": True,
    })

    return df


# ---------------------------------------------------------------------------
# 4. INTRODUCE REALISTIC DIRTINESS (missing values, dupes, bad values)
# ---------------------------------------------------------------------------
def dirty_the_data(df):
    df = df.copy()
    n = len(df)

    # Missing values in a few realistic columns
    for col, frac in [
        ("waiting_time_minutes", 0.02),
        ("weather_condition", 0.03),
        ("energy_consumed_kwh", 0.01),
        ("vehicle_type", 0.005),
        ("charging_cost", 0.01),
    ]:
        idx = rng.choice(n, size=int(n * frac), replace=False)
        df.loc[idx, col] = np.nan

    # Negative values (data entry / sensor errors)
    idx = rng.choice(n, size=int(n * 0.004), replace=False)
    df.loc[idx, "energy_consumed_kwh"] = -df.loc[idx, "energy_consumed_kwh"]

    idx = rng.choice(n, size=int(n * 0.004), replace=False)
    df.loc[idx, "revenue"] = -df.loc[idx, "revenue"].abs()

    # Impossible / absurd waiting times (sensor glitch)
    idx = rng.choice(n, size=int(n * 0.002), replace=False)
    df.loc[idx, "waiting_time_minutes"] = rng.uniform(500, 2000, size=len(idx))

    # Invalid / zero charging duration
    idx = rng.choice(n, size=int(n * 0.003), replace=False)
    df.loc[idx, "charging_duration_minutes"] = 0

    # Inconsistent station name casing/whitespace (same station_id, dirty name)
    idx = rng.choice(n, size=int(n * 0.02), replace=False)
    df.loc[idx, "station_name"] = df.loc[idx, "station_name"].str.upper() + "  "

    # Duplicate rows (exact dupes -- common in event-log ingestion / retries)
    dupe_sample = df.sample(n=int(n * 0.01), random_state=1)
    df = pd.concat([df, dupe_sample], ignore_index=True)

    # A few duplicated session_ids with different payloads (id collision bug)
    collision_idx = rng.choice(len(df), size=200, replace=False)
    df.loc[collision_idx[:100], "session_id"] = df.loc[collision_idx[100:], "session_id"].to_numpy()

    # Invalid date types as strings mixed in (simulate export inconsistency) -- keep as object dtype issue
    # (Represented by leaving 'date' as python date objects; cleaning step will standardize.)

    # Incorrect dtype: some numeric fields stored as strings with stray characters
    df["energy_consumed_kwh"] = df["energy_consumed_kwh"].astype(object)
    idx = rng.choice(len(df), size=int(len(df) * 0.005), replace=False)
    df.loc[idx, "energy_consumed_kwh"] = df.loc[idx, "energy_consumed_kwh"].astype(str) + " kWh"

    # Shuffle row order to mimic real ingestion (not sorted)
    df = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
    return df


def main():
    print("Building station master...")
    stations_df = build_station_master()
    print(f"  {len(stations_df)} stations created across {stations_df['city'].nunique()} cities.")

    print("Generating charging sessions...")
    sessions_df = generate_sessions(stations_df, N_SESSIONS)
    print(f"  {len(sessions_df)} clean sessions generated.")

    print("Introducing realistic data-quality issues...")
    dirty_df = dirty_the_data(sessions_df)
    print(f"  Final raw row count (incl. duplicates): {len(dirty_df)}")

    stations_df.to_csv("data/raw/station_master.csv", index=False)
    dirty_df.to_csv("data/raw/ev_charging_raw.csv", index=False)
    print("Saved data/raw/ev_charging_raw.csv and data/raw/station_master.csv")


if __name__ == "__main__":
    main()
