# Key Findings — EV Charging Station Utilization & Demand Analytics

*All figures below are computed directly from the cleaned/feature-engineered synthetic dataset
(`data/processed/ev_charging_features.csv`, 84,902 sessions across 73 stations).*

1. **Total charging sessions analyzed:** 84,902, consuming 1,202,461 kWh and generating
   an estimated ₹14,893,010 in revenue.

2. **Average session:** 120.9 minutes of charging with an average wait of 10.2 minutes
   before a charger became available.

3. **Peak demand hour:** 19:00, with 6,967 sessions —
   consistent with an evening commute-charging pattern.

4. **Peak demand day:** Friday, with 13,477 sessions.

5. **Peak demand month:** Month 12, with 8,605 sessions,
   consistent with the mild seasonal/growth trend built into the dataset.

6. **Weekday vs weekend:** Average of 13,045 sessions/weekday vs 9,840 sessions/weekend day —
   a 32.6% higher weekday load, indicating commuter-driven rather than
   leisure-driven demand.

7. **Busiest city:** Mumbai, with 24,574 total sessions.

8. **Top 5 busiest stations (by session volume):**
   - Saket Ev Hub 1011 (Delhi): 3,299 sessions
   - Andheri Ev Hub 1016 (Mumbai): 3,156 sessions
   - Hinjewadi Ev Hub 1051 (Pune): 3,080 sessions
   - Baner Ev Hub 1062 (Pune): 3,014 sessions
   - Thane Ev Hub 1030 (Mumbai): 3,008 sessions

9. **5 lowest-volume stations:**
   - Connaught Place Ev Hub 1001 (Delhi): 309 sessions
   - Kukatpally Ev Hub 1072 (Hyderabad): 279 sessions
   - Koramangala Ev Hub 1039 (Bengaluru): 274 sessions
   - Whitefield Ev Hub 1036 (Bengaluru): 268 sessions
   - Baner Ev Hub 1063 (Pune): 244 sessions

10. **Average station utilization rate:** 10.1% (see `station_utilization.csv` for the full
    breakdown and methodology). 0 stations
    are classified CRITICAL, 2 are HIGH,
    7 are MODERATE, and
    64 are LOW utilization.

11. **Capacity risk:** 2 stations are at CRITICAL capacity risk and 5
    at HIGH risk (see `capacity_risk.csv`). These are the stations where wait times and sessions-per-charger
    are simultaneously elevated.

12. **Underutilized infrastructure:** 64 stations show LOW utilization — expanding
    charger count at these locations is not currently justified by demand.

## Business Recommendations

1. **Prioritize charger expansion at CRITICAL capacity-risk stations first** — these 2
   stations combine high utilization, long waits, and high sessions-per-charger; they are the stations most
   likely to be losing customers to queue abandonment or competitor stations.
2. **Do not add chargers at LOW-utilization stations** — the 64 LOW-utilization stations
   have spare capacity; capital is better spent elsewhere.
3. **Introduce peak-hour pricing around 19:00** to smooth demand — shifting even a
   modest share of peak-hour sessions to off-peak hours would reduce wait times without adding infrastructure.
4. **Encourage off-peak/overnight charging** (discounted overnight rates) to flatten the 19:00
   peak and make better use of the overnight base-load capacity that already exists.
5. **Focus new-station siting on Mumbai** and other high-demand cities/areas identified in
   `demand_by_station.csv`, where demand already outstrips what a single additional station would relieve.

*Note: this project uses a synthetic dataset built with realistic statistical relationships. Absolute
figures (revenue, session counts) are illustrative of the analytical approach, not real-world EV
charging network data.*
