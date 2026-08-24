"""
analysis.py
===========
Station utilization, demand, and capacity-risk analysis.

Utilization formula
--------------------
For a given station-hour, define capacity as:

    hourly_capacity = number_of_chargers * MAX_SESSIONS_PER_CHARGER_PER_HOUR

MAX_SESSIONS_PER_CHARGER_PER_HOUR is set to 3, based on the 25th percentile of
observed charging_duration_minutes (~20 min) plus turnover overhead -- i.e. a
charger can realistically complete about 3 short sessions per hour if run back
to back. This is a documented assumption, not a fact; it is deliberately
conservative (slow AC sessions run much longer than this, so true AC-station
utilization will appear structurally lower, which is expected and noted in
the findings).

    utilization_rate (station-hour) = sessions_in_hour / hourly_capacity

Station utilization_rate (overall) = mean of station-hour utilization_rate
across all observed hours for that station, restricted to hours where the
station was open/active (i.e. had >= 1 session on that date -- otherwise
"0 sessions at 3am" would drag every station toward the same low number and
hide real differences).

Utilization classification thresholds (documented, adjustable):
    LOW       : utilization_rate < 0.15
    MODERATE  : 0.15 <= utilization_rate < 0.35
    HIGH      : 0.35 <= utilization_rate < 0.60
    CRITICAL  : utilization_rate >= 0.60

Capacity-risk score
--------------------
Combines three signals per station (each min-max normalized 0-1 across stations):
    - utilization_rate
    - average waiting_time_minutes
    - sessions_per_charger (station total sessions / number_of_chargers)

    capacity_risk_score = 0.4*utilization_norm + 0.35*wait_norm + 0.25*sessions_per_charger_norm

Capacity-risk classification:
    LOW      : score < 0.25
    MEDIUM   : 0.25 <= score < 0.50
    HIGH     : 0.50 <= score < 0.75
    CRITICAL : score >= 0.75

Run:
    python python/analysis.py
Reads:
    data/processed/ev_charging_features.csv
Produces:
    data/processed/station_utilization.csv
    data/processed/capacity_risk.csv
    data/processed/demand_summary.csv
    reports/key_findings.md
    reports/executive_summary.md
"""

import numpy as np
import pandas as pd

IN_PATH = "data/processed/ev_charging_features.csv"

MAX_SESSIONS_PER_CHARGER_PER_HOUR = 3


def normalize(s):
    return (s - s.min()) / (s.max() - s.min())


def classify_utilization(u):
    if u < 0.15:
        return "LOW"
    elif u < 0.35:
        return "MODERATE"
    elif u < 0.60:
        return "HIGH"
    else:
        return "CRITICAL"


def classify_risk(r):
    if r < 0.25:
        return "LOW"
    elif r < 0.50:
        return "MEDIUM"
    elif r < 0.75:
        return "HIGH"
    else:
        return "CRITICAL"


def station_utilization_analysis(df):
    # station-hour level session counts (only hours with activity, per station-date)
    station_hour = (
        df.groupby(["station_id", "station_name", "city", "area", "number_of_chargers", "date", "hour"])
        .size()
        .reset_index(name="sessions_in_hour")
    )
    station_hour["hourly_capacity"] = station_hour["number_of_chargers"] * MAX_SESSIONS_PER_CHARGER_PER_HOUR
    station_hour["utilization_rate"] = station_hour["sessions_in_hour"] / station_hour["hourly_capacity"]

    station_util = (
        station_hour.groupby(["station_id", "station_name", "city", "area", "number_of_chargers"])
        .agg(
            avg_utilization_rate=("utilization_rate", "mean"),
            peak_utilization_rate=("utilization_rate", "max"),
            active_station_hours=("sessions_in_hour", "count"),
            total_sessions=("sessions_in_hour", "sum"),
        )
        .reset_index()
    )
    station_util["utilization_classification"] = station_util["avg_utilization_rate"].apply(classify_utilization)

    # utilization by hour-of-day (overall, across all stations) -- for demand-intelligence page
    util_by_hour = (
        station_hour.groupby("hour")["utilization_rate"].mean().reset_index().sort_values("hour")
    )

    # utilization by location (city)
    util_by_city = (
        station_util.groupby("city")["avg_utilization_rate"].mean().reset_index().sort_values(
            "avg_utilization_rate", ascending=False
        )
    )

    return station_util, util_by_hour, util_by_city


def demand_analysis(df):
    demand_by_hour = df.groupby("hour").size().reset_index(name="sessions").sort_values("hour")
    demand_by_dow = df.groupby("day_of_week").size().reset_index(name="sessions").sort_values("day_of_week")
    demand_by_month = df.groupby("month").size().reset_index(name="sessions").sort_values("month")
    demand_weekend_vs_weekday = df.groupby("is_weekend").size().reset_index(name="sessions")
    demand_by_station = (
        df.groupby(["station_id", "station_name", "city"])
        .size()
        .reset_index(name="sessions")
        .sort_values("sessions", ascending=False)
    )
    demand_by_city = df.groupby("city").size().reset_index(name="sessions").sort_values("sessions", ascending=False)

    return {
        "by_hour": demand_by_hour,
        "by_dow": demand_by_dow,
        "by_month": demand_by_month,
        "weekend_vs_weekday": demand_weekend_vs_weekday,
        "by_station": demand_by_station,
        "by_city": demand_by_city,
    }


def capacity_analysis(df, station_util):
    station_totals = (
        df.groupby(["station_id", "station_name", "city", "area", "number_of_chargers"])
        .agg(
            total_sessions=("session_id", "count"),
            avg_wait_time=("waiting_time_minutes", "mean"),
            total_revenue=("revenue", "sum"),
        )
        .reset_index()
    )
    station_totals["sessions_per_charger"] = station_totals["total_sessions"] / station_totals["number_of_chargers"]

    merged = station_totals.merge(
        station_util[["station_id", "avg_utilization_rate", "utilization_classification"]],
        on="station_id",
        how="left",
    )

    merged["utilization_norm"] = normalize(merged["avg_utilization_rate"])
    merged["wait_norm"] = normalize(merged["avg_wait_time"])
    merged["sessions_per_charger_norm"] = normalize(merged["sessions_per_charger"])

    merged["capacity_risk_score"] = (
        0.4 * merged["utilization_norm"] + 0.35 * merged["wait_norm"] + 0.25 * merged["sessions_per_charger_norm"]
    ).round(4)
    merged["capacity_risk"] = merged["capacity_risk_score"].apply(classify_risk)

    def expansion_priority(row):
        if row["capacity_risk"] == "CRITICAL":
            return "HIGH"
        elif row["capacity_risk"] == "HIGH":
            return "MEDIUM"
        else:
            return "LOW"

    merged["expansion_priority"] = merged.apply(expansion_priority, axis=1)
    merged = merged.sort_values("capacity_risk_score", ascending=False).reset_index(drop=True)
    return merged


def main():
    df = pd.read_csv(IN_PATH)
    df["date"] = pd.to_datetime(df["date"])

    print("Running station utilization analysis...")
    station_util, util_by_hour, util_by_city = station_utilization_analysis(df)
    station_util.to_csv("data/processed/station_utilization.csv", index=False)
    print(station_util["utilization_classification"].value_counts())

    print("\nRunning demand analysis...")
    demand = demand_analysis(df)
    demand["by_station"].to_csv("data/processed/demand_by_station.csv", index=False)
    demand["by_hour"].to_csv("data/processed/demand_by_hour.csv", index=False)

    print("\nRunning capacity risk analysis...")
    capacity = capacity_analysis(df, station_util)
    capacity.to_csv("data/processed/capacity_risk.csv", index=False)
    print(capacity["capacity_risk"].value_counts())

    # ------------------------------------------------------------------
    # Build reports/key_findings.md and reports/executive_summary.md from ACTUAL computed values
    # ------------------------------------------------------------------
    total_sessions = len(df)
    total_energy = df["energy_consumed_kwh"].sum()
    total_revenue = df["revenue"].sum()
    avg_duration = df["charging_duration_minutes"].mean()
    avg_wait = df["waiting_time_minutes"].mean()
    avg_util = station_util["avg_utilization_rate"].mean()

    peak_hour_row = demand["by_hour"].sort_values("sessions", ascending=False).iloc[0]
    peak_dow_row = demand["by_dow"].sort_values("sessions", ascending=False).iloc[0]
    dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    peak_month_row = demand["by_month"].sort_values("sessions", ascending=False).iloc[0]

    top5_busiest = demand["by_station"].head(5)
    bottom5_quiet = demand["by_station"].tail(5)
    top_city = demand["by_city"].iloc[0]

    critical_stations = capacity[capacity["capacity_risk"] == "CRITICAL"]
    high_stations = capacity[capacity["capacity_risk"] == "HIGH"]
    low_util_stations = station_util[station_util["utilization_classification"] == "LOW"]

    weekend_sessions = demand["weekend_vs_weekday"].set_index("is_weekend")["sessions"]
    weekday_avg = weekend_sessions.get(False, 0) / 5
    weekend_avg = weekend_sessions.get(True, 0) / 2

    findings = f"""# Key Findings — EV Charging Station Utilization & Demand Analytics

*All figures below are computed directly from the cleaned/feature-engineered synthetic dataset
(`data/processed/ev_charging_features.csv`, {total_sessions:,} sessions across {station_util.shape[0]} stations).*

1. **Total charging sessions analyzed:** {total_sessions:,}, consuming {total_energy:,.0f} kWh and generating
   an estimated ₹{total_revenue:,.0f} in revenue.

2. **Average session:** {avg_duration:.1f} minutes of charging with an average wait of {avg_wait:.1f} minutes
   before a charger became available.

3. **Peak demand hour:** {int(peak_hour_row['hour']):02d}:00, with {int(peak_hour_row['sessions']):,} sessions —
   consistent with an evening commute-charging pattern.

4. **Peak demand day:** {dow_names[int(peak_dow_row['day_of_week'])]}, with {int(peak_dow_row['sessions']):,} sessions.

5. **Peak demand month:** Month {int(peak_month_row['month'])}, with {int(peak_month_row['sessions']):,} sessions,
   consistent with the mild seasonal/growth trend built into the dataset.

6. **Weekday vs weekend:** Average of {weekday_avg:,.0f} sessions/weekday vs {weekend_avg:,.0f} sessions/weekend day —
   a {(weekday_avg/weekend_avg - 1)*100:.1f}% higher weekday load, indicating commuter-driven rather than
   leisure-driven demand.

7. **Busiest city:** {top_city['city']}, with {int(top_city['sessions']):,} total sessions.

8. **Top 5 busiest stations (by session volume):**
{chr(10).join(f"   - {r.station_name} ({r.city}): {int(r.sessions):,} sessions" for r in top5_busiest.itertuples())}

9. **5 lowest-volume stations:**
{chr(10).join(f"   - {r.station_name} ({r.city}): {int(r.sessions):,} sessions" for r in bottom5_quiet.itertuples())}

10. **Average station utilization rate:** {avg_util*100:.1f}% (see `station_utilization.csv` for the full
    breakdown and methodology). {int((station_util['utilization_classification']=='CRITICAL').sum())} stations
    are classified CRITICAL, {int((station_util['utilization_classification']=='HIGH').sum())} are HIGH,
    {int((station_util['utilization_classification']=='MODERATE').sum())} are MODERATE, and
    {int((station_util['utilization_classification']=='LOW').sum())} are LOW utilization.

11. **Capacity risk:** {len(critical_stations)} stations are at CRITICAL capacity risk and {len(high_stations)}
    at HIGH risk (see `capacity_risk.csv`). These are the stations where wait times and sessions-per-charger
    are simultaneously elevated.

12. **Underutilized infrastructure:** {len(low_util_stations)} stations show LOW utilization — expanding
    charger count at these locations is not currently justified by demand.

## Business Recommendations

1. **Prioritize charger expansion at CRITICAL capacity-risk stations first** — these {len(critical_stations)}
   stations combine high utilization, long waits, and high sessions-per-charger; they are the stations most
   likely to be losing customers to queue abandonment or competitor stations.
2. **Do not add chargers at LOW-utilization stations** — the {len(low_util_stations)} LOW-utilization stations
   have spare capacity; capital is better spent elsewhere.
3. **Introduce peak-hour pricing around {int(peak_hour_row['hour']):02d}:00** to smooth demand — shifting even a
   modest share of peak-hour sessions to off-peak hours would reduce wait times without adding infrastructure.
4. **Encourage off-peak/overnight charging** (discounted overnight rates) to flatten the {int(peak_hour_row['hour']):02d}:00
   peak and make better use of the overnight base-load capacity that already exists.
5. **Focus new-station siting on {top_city['city']}** and other high-demand cities/areas identified in
   `demand_by_station.csv`, where demand already outstrips what a single additional station would relieve.

*Note: this project uses a synthetic dataset built with realistic statistical relationships. Absolute
figures (revenue, session counts) are illustrative of the analytical approach, not real-world EV
charging network data.*
"""

    with open("reports/key_findings.md", "w") as f:
        f.write(findings)

    exec_summary = f"""# Executive Summary — EV Charging Station Utilization & Demand Analytics

## Objective
Analyze EV charging session data to understand demand patterns, station-level utilization,
capacity bottlenecks, and produce data-driven infrastructure recommendations.

## Headline Numbers
- **{total_sessions:,}** charging sessions analyzed across **{station_util.shape[0]}** stations in
  **{df['city'].nunique()}** cities.
- **{total_energy:,.0f} kWh** delivered, **₹{total_revenue:,.0f}** in revenue.
- **{avg_util*100:.1f}%** average station utilization; **{len(critical_stations)}** stations at CRITICAL
  capacity risk.
- Peak demand at **{int(peak_hour_row['hour']):02d}:00** on **{dow_names[int(peak_dow_row['day_of_week'])]}s**.

## What This Means for the Business
Demand is concentrated in predictable commute-hour windows and in a small subset of stations, while
a meaningful share of the network is underutilized. This is a classic uneven-load problem: the fix is
not "add chargers everywhere" but targeted expansion at the identified CRITICAL/HIGH risk stations,
combined with demand-shifting (pricing, off-peak incentives) to relieve pressure without capital spend
at the busiest locations.

## Recommended Next Steps
1. Fund expansion at the CRITICAL-risk stations identified in `capacity_risk.csv`.
2. Pilot peak-hour pricing at the top 5 busiest stations.
3. Re-run this analysis quarterly as new session data accumulates, to track whether interventions
   reduce wait times and flatten peak-hour concentration.

*Full methodology, thresholds, and the complete findings list are in `key_findings.md` and the
Python/SQL analysis scripts in this repository.*
"""

    with open("reports/executive_summary.md", "w") as f:
        f.write(exec_summary)

    print("\nSaved reports/key_findings.md and reports/executive_summary.md")


if __name__ == "__main__":
    main()
