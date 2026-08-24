-- ============================================================================
-- station_analysis.sql
-- Station-level performance queries (rankings, utilization, revenue)
-- ============================================================================

-- 1. Top 10 stations by total sessions
SELECT
    s.station_id,
    s.station_name,
    s.city,
    COUNT(*) AS total_sessions
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.station_id, s.station_name, s.city
ORDER BY total_sessions DESC
LIMIT 10;


-- 2. Top 10 stations by total revenue
SELECT
    s.station_id,
    s.station_name,
    s.city,
    ROUND(SUM(cs.revenue), 2) AS total_revenue
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.station_id, s.station_name, s.city
ORDER BY total_revenue DESC
LIMIT 10;


-- 3. Top 10 stations by total energy consumption (kWh)
SELECT
    s.station_id,
    s.station_name,
    s.city,
    ROUND(SUM(cs.energy_consumed_kwh), 2) AS total_energy_kwh
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.station_id, s.station_name, s.city
ORDER BY total_energy_kwh DESC
LIMIT 10;


-- 4. Average charging duration and waiting time per station,
--    ranked by average waiting time (worst first) using RANK()
SELECT
    s.station_id,
    s.station_name,
    ROUND(AVG(cs.charging_duration_minutes), 1) AS avg_duration_min,
    ROUND(AVG(cs.waiting_time_minutes), 1) AS avg_wait_min,
    RANK() OVER (ORDER BY AVG(cs.waiting_time_minutes) DESC) AS wait_time_rank
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.station_id, s.station_name;


-- 5. Revenue per charger (normalizes revenue by station size, fairer comparison
--    than raw revenue -- a 10-bay station will naturally out-earn a 2-bay station)
SELECT
    s.station_id,
    s.station_name,
    s.number_of_chargers,
    ROUND(SUM(cs.revenue), 2) AS total_revenue,
    ROUND(SUM(cs.revenue) / s.number_of_chargers, 2) AS revenue_per_charger
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.station_id, s.station_name, s.number_of_chargers
ORDER BY revenue_per_charger DESC;


-- 6. Sessions per charger per station (load-per-bay), with a CASE-based
--    load classification
SELECT
    s.station_id,
    s.station_name,
    s.number_of_chargers,
    COUNT(*) AS total_sessions,
    ROUND(COUNT(*)::NUMERIC / s.number_of_chargers, 1) AS sessions_per_charger,
    CASE
        WHEN COUNT(*)::NUMERIC / s.number_of_chargers >= 800 THEN 'VERY HIGH LOAD'
        WHEN COUNT(*)::NUMERIC / s.number_of_chargers >= 500 THEN 'HIGH LOAD'
        WHEN COUNT(*)::NUMERIC / s.number_of_chargers >= 250 THEN 'MODERATE LOAD'
        ELSE 'LOW LOAD'
    END AS load_classification
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.station_id, s.station_name, s.number_of_chargers
ORDER BY sessions_per_charger DESC;


-- 7. Station ranking within each city (window function partitioned by city) --
--    useful for "best station in each city" style dashboard drill-through
WITH station_totals AS (
    SELECT
        s.station_id,
        s.station_name,
        s.city,
        COUNT(*) AS total_sessions,
        SUM(cs.revenue) AS total_revenue
    FROM charging_sessions cs
    JOIN stations s ON s.station_id = cs.station_id
    GROUP BY s.station_id, s.station_name, s.city
)
SELECT
    city,
    station_name,
    total_sessions,
    ROUND(total_revenue, 2) AS total_revenue,
    RANK() OVER (PARTITION BY city ORDER BY total_revenue DESC) AS city_revenue_rank
FROM station_totals
ORDER BY city, city_revenue_rank;
