-- ============================================================================
-- capacity_analysis.sql
-- Utilization, capacity-risk, and expansion-priority queries
-- ============================================================================

-- 15. Station-hour utilization rate
--     Assumption (documented, matches python/analysis.py): a charger can complete
--     ~3 sessions/hour at full back-to-back turnover -> hourly_capacity = chargers * 3
WITH station_hour AS (
    SELECT
        s.station_id,
        s.station_name,
        s.number_of_chargers,
        cs.session_date,
        cs.hour,
        COUNT(*) AS sessions_in_hour
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.station_name, s.number_of_chargers, cs.session_date, cs.hour
)
SELECT
    station_id,
    station_name,
    ROUND(AVG(sessions_in_hour::NUMERIC / (number_of_chargers * 3)), 3) AS avg_utilization_rate,
    ROUND(MAX(sessions_in_hour::NUMERIC / (number_of_chargers * 3)), 3) AS peak_utilization_rate
FROM station_hour
GROUP BY station_id, station_name
ORDER BY avg_utilization_rate DESC;


-- 16. Utilization classification (LOW / MODERATE / HIGH / CRITICAL) per station
WITH station_hour AS (
    SELECT
        s.station_id,
        s.station_name,
        s.number_of_chargers,
        cs.session_date,
        cs.hour,
        COUNT(*) AS sessions_in_hour
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.station_name, s.number_of_chargers, cs.session_date, cs.hour
),
station_util AS (
    SELECT
        station_id,
        station_name,
        AVG(sessions_in_hour::NUMERIC / (number_of_chargers * 3)) AS avg_utilization_rate
    FROM station_hour
    GROUP BY station_id, station_name
)
SELECT
    station_id,
    station_name,
    ROUND(avg_utilization_rate, 3) AS avg_utilization_rate,
    CASE
        WHEN avg_utilization_rate >= 0.60 THEN 'CRITICAL'
        WHEN avg_utilization_rate >= 0.35 THEN 'HIGH'
        WHEN avg_utilization_rate >= 0.15 THEN 'MODERATE'
        ELSE 'LOW'
    END AS utilization_classification
FROM station_util
ORDER BY avg_utilization_rate DESC;


-- 17. Underutilized stations (LOW utilization AND below-median sessions-per-charger) --
--     candidates where additional infrastructure spend is NOT currently justified
WITH station_hour AS (
    SELECT
        s.station_id, s.station_name, s.number_of_chargers,
        cs.session_date, cs.hour, COUNT(*) AS sessions_in_hour
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.station_name, s.number_of_chargers, cs.session_date, cs.hour
),
station_util AS (
    SELECT station_id, station_name, number_of_chargers,
           AVG(sessions_in_hour::NUMERIC / (number_of_chargers * 3)) AS avg_utilization_rate
    FROM station_hour
    GROUP BY station_id, station_name, number_of_chargers
),
station_load AS (
    SELECT s.station_id, COUNT(*)::NUMERIC / s.number_of_chargers AS sessions_per_charger
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.number_of_chargers
)
SELECT
    u.station_name,
    ROUND(u.avg_utilization_rate, 3) AS avg_utilization_rate,
    ROUND(l.sessions_per_charger, 1) AS sessions_per_charger
FROM station_util u
JOIN station_load l ON l.station_id = u.station_id
WHERE u.avg_utilization_rate < 0.15
  AND l.sessions_per_charger < (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sessions_per_charger) FROM station_load)
ORDER BY u.avg_utilization_rate ASC;


-- 18. Capacity-risk score & expansion priority per station
--     score = 0.4*utilization_norm + 0.35*wait_norm + 0.25*sessions_per_charger_norm  (all min-max normalized)
WITH station_agg AS (
    SELECT
        s.station_id,
        s.station_name,
        s.number_of_chargers,
        COUNT(*) AS total_sessions,
        AVG(cs.waiting_time_minutes) AS avg_wait,
        COUNT(*)::NUMERIC / s.number_of_chargers AS sessions_per_charger
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.station_name, s.number_of_chargers
),
station_hour AS (
    SELECT s.station_id, s.number_of_chargers, cs.session_date, cs.hour, COUNT(*) AS sessions_in_hour
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.number_of_chargers, cs.session_date, cs.hour
),
station_util AS (
    SELECT station_id, AVG(sessions_in_hour::NUMERIC / (number_of_chargers * 3)) AS avg_utilization_rate
    FROM station_hour
    GROUP BY station_id
),
bounds AS (
    SELECT
        MIN(u.avg_utilization_rate) AS util_min, MAX(u.avg_utilization_rate) AS util_max,
        MIN(a.avg_wait) AS wait_min, MAX(a.avg_wait) AS wait_max,
        MIN(a.sessions_per_charger) AS spc_min, MAX(a.sessions_per_charger) AS spc_max
    FROM station_agg a JOIN station_util u ON u.station_id = a.station_id
)
SELECT
    a.station_name,
    ROUND(u.avg_utilization_rate, 3) AS avg_utilization_rate,
    ROUND(a.avg_wait, 1) AS avg_wait_min,
    ROUND(a.sessions_per_charger, 1) AS sessions_per_charger,
    ROUND(
        0.4 * (u.avg_utilization_rate - b.util_min) / NULLIF(b.util_max - b.util_min, 0)
      + 0.35 * (a.avg_wait - b.wait_min) / NULLIF(b.wait_max - b.wait_min, 0)
      + 0.25 * (a.sessions_per_charger - b.spc_min) / NULLIF(b.spc_max - b.spc_min, 0)
    , 3) AS capacity_risk_score,
    CASE
        WHEN (0.4 * (u.avg_utilization_rate - b.util_min) / NULLIF(b.util_max - b.util_min, 0)
            + 0.35 * (a.avg_wait - b.wait_min) / NULLIF(b.wait_max - b.wait_min, 0)
            + 0.25 * (a.sessions_per_charger - b.spc_min) / NULLIF(b.spc_max - b.spc_min, 0)) >= 0.75 THEN 'HIGH'
        WHEN (0.4 * (u.avg_utilization_rate - b.util_min) / NULLIF(b.util_max - b.util_min, 0)
            + 0.35 * (a.avg_wait - b.wait_min) / NULLIF(b.wait_max - b.wait_min, 0)
            + 0.25 * (a.sessions_per_charger - b.spc_min) / NULLIF(b.spc_max - b.spc_min, 0)) >= 0.50 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS expansion_priority
FROM station_agg a
JOIN station_util u ON u.station_id = a.station_id
CROSS JOIN bounds b
ORDER BY capacity_risk_score DESC;


-- 19. Average waiting time by utilization tier -- validates the core hypothesis
--     that higher utilization correlates with longer waits
WITH station_hour AS (
    SELECT s.station_id, s.number_of_chargers, cs.session_date, cs.hour, COUNT(*) AS sessions_in_hour
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.number_of_chargers, cs.session_date, cs.hour
),
station_util AS (
    SELECT station_id, AVG(sessions_in_hour::NUMERIC / (number_of_chargers * 3)) AS avg_utilization_rate
    FROM station_hour
    GROUP BY station_id
),
classified AS (
    SELECT station_id,
        CASE
            WHEN avg_utilization_rate >= 0.60 THEN 'CRITICAL'
            WHEN avg_utilization_rate >= 0.35 THEN 'HIGH'
            WHEN avg_utilization_rate >= 0.15 THEN 'MODERATE'
            ELSE 'LOW'
        END AS utilization_classification
    FROM station_util
)
SELECT
    c.utilization_classification,
    COUNT(DISTINCT c.station_id) AS n_stations,
    ROUND(AVG(cs.waiting_time_minutes), 1) AS avg_wait_min
FROM classified c
JOIN charging_sessions cs ON cs.station_id = c.station_id
GROUP BY c.utilization_classification
ORDER BY avg_wait_min DESC;
