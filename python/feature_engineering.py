"""
feature_engineering.py
=======================
Builds analytical features on top of the cleaned dataset.

Metric definitions
-------------------
session_duration            = charging_duration_minutes (already computed at session grain)
energy_per_minute            = energy_consumed_kwh / charging_duration_minutes
revenue_per_kwh               = revenue / energy_consumed_kwh
revenue_per_session            = revenue (session grain) -- also aggregated at station/day grain
is_weekend                   = day_of_week in {5, 6} (Sat, Sun)
is_peak_hour                 = hour in {8, 9, 18, 19, 20} (same definition as EDA peak-hour weighting)
station_daily_sessions       = COUNT(sessions) per station_id per date
station_hourly_sessions      = COUNT(sessions) per station_id per date per hour
station_revenue               = SUM(revenue) per station_id per date
station_energy_consumption   = SUM(energy_consumed_kwh) per station_id per date
average_wait_time            = MEAN(waiting_time_minutes) per station_id per date

utilization_rate (station-hour grain)
  = sessions_in_hour / (number_of_chargers * max_sessions_per_charger_per_hour)
  where max_sessions_per_charger_per_hour is a capacity constant derived from the
  minimum realistic session length (see analysis.py for the full formula + justification).
  Feature engineering here produces the raw building blocks (sessions_in_hour, chargers);
  the utilization % itself is computed in analysis.py where the capacity assumption is documented
  alongside the utilization classification thresholds.

capacity_pressure (station-day grain)
  = average_wait_time (that day) combined with sessions-per-charger, also finalized in
  capacity analysis (analysis.py) using both engineered pieces here.

Run:
    python python/feature_engineering.py
Reads:
    data/processed/ev_charging_cleaned.csv
Produces:
    data/processed/ev_charging_features.csv
"""

import numpy as np
import pandas as pd

IN_PATH = "data/processed/ev_charging_cleaned.csv"
OUT_PATH = "data/processed/ev_charging_features.csv"


def build_features(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])

    # --- Session-grain time features ---
    df["session_duration"] = df["charging_duration_minutes"]
    df["week"] = df["start_time"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = df["day_of_week"].isin([5, 6])
    df["is_peak_hour"] = df["peak_hour"].astype(bool)

    # --- Session-grain efficiency/financial features ---
    df["energy_per_minute"] = (df["energy_consumed_kwh"] / df["charging_duration_minutes"]).replace(
        [np.inf, -np.inf], np.nan
    )
    df["revenue_per_kwh"] = (df["revenue"] / df["energy_consumed_kwh"]).replace([np.inf, -np.inf], np.nan)
    df["revenue_per_session"] = df["revenue"]

    # --- Station x Date aggregates (joined back onto session rows) ---
    station_daily = (
        df.groupby(["station_id", "date"])
        .agg(
            station_daily_sessions=("session_id", "count"),
            station_revenue=("revenue", "sum"),
            station_energy_consumption=("energy_consumed_kwh", "sum"),
            average_wait_time=("waiting_time_minutes", "mean"),
        )
        .reset_index()
    )
    df = df.merge(station_daily, on=["station_id", "date"], how="left")

    # --- Station x Date x Hour aggregate (for utilization-by-hour analysis) ---
    station_hourly = (
        df.groupby(["station_id", "date", "hour"])
        .agg(station_hourly_sessions=("session_id", "count"))
        .reset_index()
    )
    df = df.merge(station_hourly, on=["station_id", "date", "hour"], how="left")

    # --- Sessions per charger per day (building block for capacity_pressure) ---
    df["sessions_per_charger_daily"] = df["station_daily_sessions"] / df["number_of_chargers"]

    # --- capacity_pressure: composite 0-1+ score combining wait time and load-per-charger.
    #     Both components are min-max normalized across the dataset so they contribute comparably;
    #     finalized/classified into LOW-CRITICAL tiers in analysis.py.
    wait_norm = (df["average_wait_time"] - df["average_wait_time"].min()) / (
        df["average_wait_time"].max() - df["average_wait_time"].min()
    )
    load_norm = (df["sessions_per_charger_daily"] - df["sessions_per_charger_daily"].min()) / (
        df["sessions_per_charger_daily"].max() - df["sessions_per_charger_daily"].min()
    )
    df["capacity_pressure"] = (0.5 * wait_norm + 0.5 * load_norm).round(4)

    return df


def main():
    df = pd.read_csv(IN_PATH)
    featured = build_features(df)
    featured.to_csv(OUT_PATH, index=False)
    print(f"Feature-engineered dataset saved to {OUT_PATH}")
    print(f"Rows: {len(featured)}, Columns: {len(featured.columns)}")
    print("New columns added:", [c for c in featured.columns if c not in df.columns])


if __name__ == "__main__":
    main()
