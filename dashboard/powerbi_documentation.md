# Power BI Dashboard Documentation
## EV Charging Station Utilization & Demand Analytics

This document specifies the Power BI dashboard design so it can be rebuilt exactly from
`data/processed/ev_charging_features.csv` (+ `station_utilization.csv` and `capacity_risk.csv`
for the pre-computed analytical tables). It is written as a build spec, not a screenshot
description, since a live .pbix file can't be produced outside Power BI Desktop itself.

## Data Model

Import as separate tables and relate them:

| Table | Source file | Key |
|---|---|---|
| `Sessions` | `ev_charging_features.csv` | `station_id` (many) |
| `StationUtilization` | `station_utilization.csv` | `station_id` (one) |
| `CapacityRisk` | `capacity_risk.csv` | `station_id` (one) |
| `Stations` (dim) | `station_master.csv` | `station_id` (one) |

Relationships: `Sessions[station_id]` → `Stations[station_id]` (many-to-one), and
`Stations[station_id]` → `StationUtilization[station_id]` / `CapacityRisk[station_id]`
(one-to-one). Mark `Stations` as the dimension table for all station-level slicers.

Add a **Date table** (`CALENDAR(MIN(Sessions[date]), MAX(Sessions[date]))`) marked as the
official date table, related to `Sessions[date]`, to enable proper time-intelligence
(MoM, rolling averages) without relying on the raw `month`/`day_of_week` columns for
anything date-hierarchy related.

## Key DAX Measures

```
Total Sessions          = COUNTROWS(Sessions)
Total Energy (kWh)      = SUM(Sessions[energy_consumed_kwh])
Total Revenue           = SUM(Sessions[revenue])
Avg Session Duration    = AVERAGE(Sessions[charging_duration_minutes])
Avg Wait Time           = AVERAGE(Sessions[waiting_time_minutes])
Avg Utilization         = AVERAGE(StationUtilization[avg_utilization_rate])
Critical Risk Stations  = CALCULATE(DISTINCTCOUNT(CapacityRisk[station_id]), CapacityRisk[capacity_risk] = "CRITICAL")
Revenue per Charger     = DIVIDE([Total Revenue], SUM(Stations[number_of_chargers]))
Sessions per Charger    = DIVIDE([Total Sessions], SUM(Stations[number_of_chargers]))
```

## Page 1 — EV Charging Executive Overview

**KPI card row (top):** Total Sessions · Total Energy (kWh) · Total Revenue ·
Avg Session Duration · Avg Waiting Time · Avg Utilization.

**Body:**
- Line chart: Sessions by Hour (X = `hour`, Y = `Total Sessions`) — shows the two-peak
  commute pattern (morning + evening).
- Line chart: Monthly Demand Trend (Date hierarchy → Month, Y = `Total Sessions`), with
  a trend line to surface the mild seasonal growth built into the dataset.
- Bar chart: Station Performance — top 10 stations by `Total Sessions`, sorted descending.
- Slicers: Date range, City.

## Page 2 — Station Performance

**Table/matrix** (station grain), columns: Station Name, City, Sessions, Revenue,
Energy Consumption (kWh), Avg Waiting Time, Avg Session Duration, Number of Chargers,
Utilization Classification — conditional-formatted (color scale) on Utilization %.

**Charts:**
- Ranked bar chart: Revenue per Charger by station.
- Scatter plot: Utilization % (X) vs Avg Waiting Time (Y), bubble size = Sessions,
  color = Utilization Classification — visually separates "healthy" vs "strained" stations.

**Filters (slicer panel):** City, Area, Station, Charger Type, Vehicle Type, Date range.

## Page 3 — Demand Intelligence

- Line/area chart: Hourly demand curve, split by Weekday vs Weekend (two series).
- Column chart: Demand by Day of Week (Mon–Sun).
- Line chart: Monthly trend with a reference line for the yearly average.
- Bar chart: Demand by City / Area (drill-down: City → Area).
- Matrix/heatmap: Day of Week (rows) × Hour (columns), values = session count,
  conditional formatting as a color scale — the classic demand heatmap.
- Card: Peak Hour, Card: Peak Day (dynamic top-N DAX measures).

## Page 4 — Capacity & Infrastructure (most important page)

- KPI cards: Critical-Risk Stations, High-Risk Stations, Underutilized (LOW) Stations.
- Table: `CapacityRisk` sorted by `capacity_risk_score` descending — columns: Station,
  City, Utilization %, Avg Wait, Sessions per Charger, Capacity Risk Score, Capacity Risk
  tier, **Expansion Priority** (HIGH/MEDIUM/LOW), conditional-formatted with a
  red/amber/green scale on `capacity_risk`.
- Bar chart: Sessions per Charger by station, reference line at the network median.
- Scatter: Capacity Risk Score (X) vs Avg Wait Time (Y), color = Expansion Priority.
- Drill-through page: click a station → detail page showing that station's hourly
  utilization curve and daily session trend (built from `Sessions` filtered to that
  `station_id`).

**Expansion Priority legend (static, matches `analysis.py` logic):**
`CRITICAL capacity_risk → HIGH priority`, `HIGH capacity_risk → MEDIUM priority`,
`MEDIUM/LOW capacity_risk → LOW priority`.

## Design Guidelines Applied

- One accent color (e.g. deep teal `#0E7C7B`) for primary KPIs, a red/amber/green
  scale reserved exclusively for risk/utilization indicators — not decorative color.
- Consistent card sizing and a 12-column grid across all four pages.
- Tooltips on every chart show the underlying raw numbers (not just the visual encoding).
- No 3D charts, no gratuitous donut charts, no more than 6 visuals per page.
- Segoe UI (Power BI default) throughout, single font-size scale (28px KPI numbers,
  14px axis labels, 11px tooltips) for visual consistency.
