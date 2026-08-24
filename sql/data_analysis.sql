-- ============================================================================
-- data_analysis.sql
-- General exploratory / financial queries
-- ============================================================================

-- 20. Overall summary KPIs (matches Power BI Page 1 header cards)
SELECT
    COUNT(*) AS total_sessions,
    ROUND(SUM(energy_consumed_kwh), 1) AS total_energy_kwh,
    ROUND(SUM(revenue), 2) AS total_revenue,
    ROUND(AVG(charging_duration_minutes), 1) AS avg_duration_min,
    ROUND(AVG(waiting_time_minutes), 1) AS avg_wait_min
FROM charging_sessions
WHERE session_status = 'Completed';


-- 21. Session status breakdown (completed / cancelled / failed) with share of total
SELECT
    session_status,
    COUNT(*) AS n_sessions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM charging_sessions
GROUP BY session_status
ORDER BY n_sessions DESC;


-- 22. Revenue and energy by charger type -- which charger technology drives the business
SELECT
    s.charger_type,
    COUNT(*) AS total_sessions,
    ROUND(SUM(cs.energy_consumed_kwh), 1) AS total_energy_kwh,
    ROUND(SUM(cs.revenue), 2) AS total_revenue,
    ROUND(SUM(cs.revenue) / NULLIF(SUM(cs.energy_consumed_kwh), 0), 2) AS revenue_per_kwh
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.charger_type
ORDER BY total_revenue DESC;


-- 23. Weather condition impact on session volume and average duration
SELECT
    weather_condition,
    COUNT(*) AS n_sessions,
    ROUND(AVG(charging_duration_minutes), 1) AS avg_duration_min
FROM charging_sessions
WHERE weather_condition IS NOT NULL AND weather_condition <> 'Unknown'
GROUP BY weather_condition
ORDER BY n_sessions DESC;
