-- ============================================================================
-- demand_analysis.sql
-- Time-based and location-based demand pattern queries
-- ============================================================================

-- 8. Peak charging hours (overall demand by hour of day)
SELECT
    hour,
    COUNT(*) AS total_sessions,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_total_sessions
FROM charging_sessions
GROUP BY hour
ORDER BY total_sessions DESC;


-- 9. Weekday vs weekend demand comparison
SELECT
    CASE WHEN day_of_week IN (5, 6) THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    COUNT(*) AS total_sessions,
    ROUND(AVG(charging_duration_minutes), 1) AS avg_duration_min,
    ROUND(AVG(waiting_time_minutes), 1) AS avg_wait_min
FROM charging_sessions
GROUP BY 1;


-- 10. Monthly demand trend with month-over-month change using LAG()
WITH monthly AS (
    SELECT month, COUNT(*) AS sessions
    FROM charging_sessions
    GROUP BY month
)
SELECT
    month,
    sessions,
    LAG(sessions) OVER (ORDER BY month) AS prev_month_sessions,
    ROUND(
        100.0 * (sessions - LAG(sessions) OVER (ORDER BY month))
        / NULLIF(LAG(sessions) OVER (ORDER BY month), 0), 2
    ) AS pct_change_mom
FROM monthly
ORDER BY month;


-- 11. Highest-demand cities and areas
SELECT
    s.city,
    s.area,
    COUNT(*) AS total_sessions,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS demand_rank
FROM charging_sessions cs
JOIN stations s ON s.station_id = cs.station_id
GROUP BY s.city, s.area
ORDER BY total_sessions DESC;


-- 12. Vehicle-type demand behavior (session count, avg energy, avg duration)
SELECT
    vehicle_type,
    COUNT(*) AS total_sessions,
    ROUND(AVG(energy_consumed_kwh), 2) AS avg_energy_kwh,
    ROUND(AVG(charging_duration_minutes), 1) AS avg_duration_min
FROM charging_sessions
GROUP BY vehicle_type
ORDER BY total_sessions DESC;


-- 13. 7-day rolling average of daily sessions (smooths day-to-day noise to reveal trend)
WITH daily AS (
    SELECT session_date, COUNT(*) AS sessions
    FROM charging_sessions
    GROUP BY session_date
)
SELECT
    session_date,
    sessions,
    ROUND(AVG(sessions) OVER (
        ORDER BY session_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ), 1) AS rolling_7day_avg_sessions
FROM daily
ORDER BY session_date;


-- 14. Stations consistently in the top-10 by daily sessions (>50% of days) --
--     identifies chronically high-demand stations vs one-off spikes
WITH daily_station AS (
    SELECT
        session_date,
        station_id,
        COUNT(*) AS sessions,
        RANK() OVER (PARTITION BY session_date ORDER BY COUNT(*) DESC) AS daily_rank
    FROM charging_sessions
    GROUP BY session_date, station_id
),
top10_days AS (
    SELECT station_id, COUNT(*) AS days_in_top10
    FROM daily_station
    WHERE daily_rank <= 10
    GROUP BY station_id
),
total_days AS (
    SELECT COUNT(DISTINCT session_date) AS n_days FROM charging_sessions
)
SELECT
    s.station_name,
    t.days_in_top10,
    ROUND(100.0 * t.days_in_top10 / td.n_days, 1) AS pct_days_in_top10
FROM top10_days t
JOIN stations s ON s.station_id = t.station_id
CROSS JOIN total_days td
WHERE t.days_in_top10 > 0.5 * td.n_days
ORDER BY pct_days_in_top10 DESC;
