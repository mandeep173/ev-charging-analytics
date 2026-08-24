# EV Charging Station Utilization & Demand Analytics

End-to-end data analytics project analyzing EV charging session data to measure station
utilization, identify demand patterns, detect capacity bottlenecks, and produce
data-driven infrastructure recommendations — built to the standard of an internal
analytics tool at a real EV charging network operator.

## Problem Statement

EV charging networks face an uneven-load problem: some stations are overwhelmed at peak
hours while others sit idle, and it isn't obvious from raw session logs alone which
stations justify capital investment in additional chargers versus which need demand
management instead. This project builds the full pipeline — from raw session data to
an executive dashboard — to answer that question with evidence rather than guesswork.

## Business Objective

1. Quantify how EV charging demand varies by hour, day, and month.
2. Measure per-station utilization against a defensible capacity model.
3. Identify stations at capacity risk (candidates for expansion) vs. underutilized
   stations (where expansion is *not* justified).
4. Turn the above into concrete, numbers-backed business recommendations.

## Dataset

A **synthetic** dataset of **84,902 cleaned charging sessions** across **73 stations**
in **5 cities** (Delhi, Mumbai, Bengaluru, Pune, Hyderabad), covering Jan–Dec 2024.

A real public dataset at this per-session granularity (timestamps, energy, revenue,
station-level detail, 50k+ rows) with no usage restrictions was not available, so the
dataset is generated (`python/data_generation.py`) with deliberate, documented
statistical relationships:
- Two daily demand peaks (morning ~8-9am, evening ~6-8pm)
- Weekday demand meaningfully higher than weekends (commuter-driven pattern)
- Mild monthly seasonality/growth trend
- Station-level demand tiers (some stations are structurally busier than others)
- Waiting time that rises with station-level congestion, not with session length
- Vehicle-type-driven energy/duration differences (2-wheelers vs SUVs vs commercial)

Realistic messiness is deliberately introduced and then cleaned: missing values,
duplicate rows, colliding session IDs, negative values, impossible waiting times,
inconsistent station-name casing, and a stray-unit-string dtype issue. All records
carry an `is_synthetic = True` flag, and this is not presented as real-world data
anywhere in the project.

## Architecture

```
Raw Data (synthetic generator)
   → Data Cleaning (documented, non-destructive)
   → Feature Engineering (14 derived analytical features)
   → Exploratory Data Analysis
   → SQL Analytics (23 queries: schema + 4 analysis files)
   → Station Utilization Analysis
   → Demand Analysis
   → Capacity Risk Analysis
   → Optional Forecasting (Random Forest, next-day sessions)
   → Power BI Dashboard (4-page spec)
   → Business Recommendations
```

## Tools Used

Python (pandas, NumPy, Matplotlib, scikit-learn) · SQL (PostgreSQL-flavored, validated
against DuckDB) · Power BI (design + DAX specification) · Jupyter Notebooks · Git

## Data Pipeline

| Step | Script | Output |
|---|---|---|
| Generate | `python/data_generation.py` | `data/raw/ev_charging_raw.csv`, `station_master.csv` |
| Clean | `python/data_cleaning.py` | `data/processed/ev_charging_cleaned.csv`, `reports/cleaning_log.md` |
| Feature engineer | `python/feature_engineering.py` | `data/processed/ev_charging_features.csv` |
| Analyze | `python/analysis.py` | `station_utilization.csv`, `capacity_risk.csv`, `demand_by_*.csv`, `reports/key_findings.md`, `reports/executive_summary.md` |

## Key Metrics & Definitions

- **Utilization rate** (station-hour) = `sessions_in_hour / (number_of_chargers × 3)`,
  where 3 = assumed max realistic sessions/charger/hour. Station-level = mean across
  active hours. Tiers: LOW (<15%), MODERATE (15–35%), HIGH (35–60%), CRITICAL (≥60%).
- **Capacity risk score** = `0.4×utilization + 0.35×avg_wait + 0.25×sessions_per_charger`
  (each min-max normalized). Tiers: LOW/MEDIUM/HIGH/CRITICAL → maps to expansion
  priority LOW/LOW/MEDIUM/HIGH.
- Full metric definitions (energy_per_minute, revenue_per_kwh, capacity_pressure, etc.)
  are documented in the `feature_engineering.py` docstring.

## Analysis Performed

- Exploratory analysis across 13 dimensions (hour, day, month, weekday/weekend,
  station, city, vehicle type, charger type, revenue, energy, waiting time, duration)
- Station utilization classification and ranking
- Demand pattern analysis (peak hours/days/months, consistently overloaded stations)
- Capacity-risk scoring and expansion-priority recommendation
- Optional experimental next-day demand forecasting (Random Forest, leakage-checked)

## Dashboard

A 4-page Power BI dashboard is fully specified in `dashboard/powerbi_documentation.md`
(data model, DAX measures, page-by-page layout, filters, and design guidelines):
**Executive Overview → Station Performance → Demand Intelligence → Capacity & Infrastructure.**

## Key Findings (from the actual computed results — see `reports/key_findings.md`)

- **84,902** sessions analyzed, **1,202,461 kWh** delivered, **₹14.89M** in estimated revenue.
- Peak demand hour: **19:00**; peak demand day: **Friday**; weekday sessions run
  **~33% higher** than weekend days — a commuter-driven pattern, not leisure-driven.
- **2 stations** are at CRITICAL capacity risk and **5** at HIGH risk.
- **64 of 73 stations** show LOW utilization — expansion is not currently justified there.

Full findings and business recommendations: `reports/key_findings.md` and
`reports/executive_summary.md`.

## Project Structure

```
ev-charging-analytics/
├── data/{raw,processed}/
├── notebooks/           # 01-07, fully executed with real output
├── python/               # data_generation, data_cleaning, feature_engineering, analysis
├── sql/                  # schema.sql + 4 analysis files, 23 validated queries
├── dashboard/            # powerbi_documentation.md
├── reports/              # executive_summary.md, key_findings.md, cleaning_log.md
├── requirements.txt
└── README.md
```

## How to Run

```bash
pip install -r requirements.txt

python python/data_generation.py       # -> data/raw/
python python/data_cleaning.py         # -> data/processed/ev_charging_cleaned.csv
python python/feature_engineering.py   # -> data/processed/ev_charging_features.csv
python python/analysis.py              # -> utilization/demand/capacity csvs + reports

# Notebooks (already pre-executed, but can be re-run):
jupyter notebook notebooks/

# SQL (example with DuckDB, no server needed):
python -c "
import duckdb
con = duckdb.connect()
con.execute(\"CREATE TABLE stations AS SELECT * FROM read_csv_auto('data/raw/station_master.csv')\")
con.execute(\"CREATE TABLE charging_sessions AS SELECT *, date AS session_date FROM read_csv_auto('data/processed/ev_charging_cleaned.csv')\")
print(con.execute(open('sql/station_analysis.sql').read().split(';')[0]).fetchdf())
"
```

## Future Improvements

- Replace the synthetic generator with a real multi-year utilization dataset if/when
  one becomes available, to validate the seasonal-growth assumption.
- Add a live Power BI connection (DirectQuery) to a production database instead of
  static CSV import, for a real operational dashboard.
- Extend the capacity-risk model with a queueing-theory-based (e.g. M/M/c) utilization
  estimate instead of the fixed sessions-per-charger-per-hour assumption.
- Add anomaly detection for individual stations with sudden demand drops (possible
  hardware faults).

## Data Disclaimer

This project uses a **synthetic dataset** built with realistic statistical relationships
for portfolio and educational purposes. Absolute figures (revenue, session counts,
station names) do not represent any real company, city, or EV charging network.
