-- Seven optimization candidates, in the same order as olap_queries.sql
-- Select your warehouse database first. Index setup is separate in olap_indexes.sql
-- Read-only reports only. No server settings, DDL, or automatic benchmarking here
-- See OLAP_OPTIMIZATION.md before running the full dataset

-- Q1a - Covering-index optimization, analytical SQL unchanged
-- Q1
-- Per-zone and per-borough categorical trip demand (weekend or late-night)
SELECT 
    COALESCE(l.borough, 'ALL BOROUGHS') AS borough,
    COALESCE(l.zone, 'Borough Subtotal') AS zone,
    SUM(CASE WHEN t.time_period = 'Late Night' AND d.is_weekend = 0 THEN 1 ELSE 0 END) AS weekday_late_night_pickups,
    SUM(CASE WHEN t.time_period = 'Late Night' AND d.is_weekend = 1 THEN 1 ELSE 0 END) AS weekend_late_night_pickups,
    SUM(CASE WHEN d.is_weekend = 1 THEN 1 ELSE 0 END) AS all_weekend_pickups,
    COUNT(f.trip_id) AS total_filtered_pickups
FROM fact_trip_records f
JOIN dim_location l ON f.pu_location_id = l.location_id
JOIN dim_date d     ON f.pu_date_id = d.date_id
JOIN dim_time t     ON f.pu_time_id = t.time_id
WHERE t.time_period = 'Late Night' 
   OR d.is_weekend = 1
GROUP BY 
    l.borough, 
    l.zone WITH ROLLUP;

-- Q1b - Count trips per active date before computing hourly averages
WITH daily_demand AS (
    SELECT l.borough, t.time_period, t.hour, d.`date` AS pickup_date,
           d.is_weekend, COUNT(f.trip_id) AS pickups
    FROM fact_trip_records f
    JOIN dim_location l ON f.pu_location_id = l.location_id
    JOIN dim_date d ON f.pu_date_id = d.date_id
    JOIN dim_time t ON f.pu_time_id = t.time_id
    GROUP BY l.borough, t.time_period, t.hour, d.`date`, d.is_weekend
)
SELECT borough, time_period, hour,
    SUM(CASE WHEN is_weekend = 0 THEN pickups ELSE 0 END) AS weekday_pickups,
    SUM(CASE WHEN is_weekend = 1 THEN pickups ELSE 0 END) AS weekend_pickups,
    ROUND(SUM(CASE WHEN is_weekend = 0 THEN pickups ELSE 0 END)
        / NULLIF(SUM(CASE WHEN is_weekend = 0 THEN 1 ELSE 0 END), 0), 2)
        AS avg_weekday_hourly_pickups,
    ROUND(SUM(CASE WHEN is_weekend = 1 THEN pickups ELSE 0 END)
        / NULLIF(SUM(CASE WHEN is_weekend = 1 THEN 1 ELSE 0 END), 0), 2)
        AS avg_weekend_hourly_pickups
FROM daily_demand
GROUP BY borough, time_period, hour
ORDER BY borough, hour;

-- Q1c - Count late-night trips by numeric location/date before descriptive joins
WITH night_counts AS (
    SELECT f.pu_location_id, f.pu_date_id, COUNT(f.trip_id) AS pickups
    FROM fact_trip_records f
    JOIN dim_time t ON f.pu_time_id = t.time_id
    WHERE t.time_period = 'Late Night'
    GROUP BY f.pu_location_id, f.pu_date_id
)
SELECT
    COALESCE(l.zone, 'ALL ZONES') AS zone,
    COALESCE(CAST(d.year AS CHAR), 'All Years') AS yr,
    COALESCE(CAST(d.quarter AS CHAR), 'Year Subtotal') AS qtr,
    COALESCE(CAST(d.month AS CHAR), 'Quarter Subtotal') AS mo,
    COALESCE(SUM(g.pickups), 0) AS late_night_pickups
FROM night_counts g
JOIN dim_location l ON g.pu_location_id = l.location_id
JOIN dim_date d ON g.pu_date_id = d.date_id
GROUP BY l.zone, d.year, d.quarter, d.month WITH ROLLUP;

-- Q2a - Aggregate payment IDs and numeric fare tiers before payment descriptions
WITH fare_groups AS (
    SELECT f.payment_id,
        CASE
            WHEN f.fare_amount < 10 THEN 1
            WHEN f.fare_amount BETWEEN 10 AND 24.99 THEN 2
            WHEN f.fare_amount BETWEEN 25 AND 49.99 THEN 3
            ELSE 4
        END AS fare_tier,
        COUNT(f.trip_id) AS trips,
        SUM(f.tip_amount) AS tip_sum,
        COUNT(f.tip_amount) AS tip_count
    FROM fact_trip_records f
    WHERE f.fare_amount > 0
    GROUP BY f.payment_id, fare_tier
)
SELECT
    CASE g.fare_tier
        WHEN 1 THEN '1. Under $10'
        WHEN 2 THEN '2. $10 - $24.99'
        WHEN 3 THEN '3. $25 - $49.99'
        WHEN 4 THEN '4. $50 and Above'
    END AS fare_range,
    SUM(CASE WHEN p.payment_method = 'Credit Card' THEN g.trips ELSE 0 END) AS credit_card_trips,
    SUM(CASE WHEN p.payment_method = 'Cash' THEN g.trips ELSE 0 END) AS cash_trips,
    SUM(CASE WHEN p.payment_method NOT IN ('Credit Card', 'Cash') THEN g.trips ELSE 0 END) AS other_payment_trips,
    COALESCE(SUM(g.trips), 0) AS total_trips,
    ROUND(SUM(g.tip_sum) / NULLIF(SUM(g.tip_count), 0), 2) AS avg_tip_amount
FROM fare_groups g
JOIN dim_payment p ON g.payment_id = p.payment_id
GROUP BY g.fare_tier WITH ROLLUP;

-- Q2b - Aggregate before joining borough/payment descriptions
WITH payment_groups AS (
    SELECT f.pu_location_id, t.time_period, f.payment_id,
        COUNT(f.trip_id) AS trips,
        SUM(f.fare_amount) AS fare_sum, COUNT(f.fare_amount) AS fare_count,
        SUM(f.tip_amount) AS tip_sum, COUNT(f.tip_amount) AS tip_count,
        SUM(f.total_amount) AS total_sum, COUNT(f.total_amount) AS total_count
    FROM fact_trip_records f
    JOIN dim_time t ON f.pu_time_id = t.time_id
    WHERE f.fare_amount > 0
    GROUP BY f.pu_location_id, t.time_period, f.payment_id
)
SELECT
    COALESCE(l.borough, 'ALL BOROUGHS') AS borough,
    COALESCE(g.time_period, 'All Time Periods') AS time_period,
    COALESCE(p.payment_method, 'All Payment Methods') AS payment_method,
    COALESCE(SUM(g.trips), 0) AS trip_count,
    ROUND(SUM(g.fare_sum) / NULLIF(SUM(g.fare_count), 0), 2) AS avg_fare,
    ROUND(SUM(g.tip_sum) / NULLIF(SUM(g.tip_count), 0), 2) AS avg_tip,
    ROUND(SUM(g.total_sum) / NULLIF(SUM(g.total_count), 0), 2) AS avg_total
FROM payment_groups g
JOIN dim_location l ON g.pu_location_id = l.location_id
JOIN dim_payment p ON g.payment_id = p.payment_id
GROUP BY l.borough, g.time_period, p.payment_method WITH ROLLUP;

-- Q3a - Aggregate numeric location/distance groups before borough rollup
WITH trip_groups AS (
    SELECT f.pu_location_id,
        CASE
            WHEN f.trip_distance < 2 THEN 1
            WHEN f.trip_distance BETWEEN 2 AND 4.99 THEN 2
            WHEN f.trip_distance BETWEEN 5 AND 9.99 THEN 3
            ELSE 4
        END AS distance_tier,
        SUM(CASE WHEN t.time_period IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                 THEN f.trip_duration_seconds / 60.0 END) AS rush_duration_sum,
        COUNT(CASE WHEN t.time_period IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                   THEN f.trip_duration_seconds END) AS rush_duration_count,
        SUM(CASE WHEN t.time_period NOT IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                 THEN f.trip_duration_seconds / 60.0 END) AS off_peak_duration_sum,
        COUNT(CASE WHEN t.time_period NOT IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                   THEN f.trip_duration_seconds END) AS off_peak_duration_count,
        SUM(CASE WHEN t.time_period IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                 THEN f.estimated_speed_mph END) AS rush_speed_sum,
        COUNT(CASE WHEN t.time_period IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                   THEN f.estimated_speed_mph END) AS rush_speed_count,
        SUM(CASE WHEN t.time_period NOT IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                 THEN f.estimated_speed_mph END) AS off_peak_speed_sum,
        COUNT(CASE WHEN t.time_period NOT IN ('Morning Rush', 'Evening Rush', 'Rush Hour')
                   THEN f.estimated_speed_mph END) AS off_peak_speed_count
    FROM fact_trip_records f
    JOIN dim_date d ON f.pu_date_id = d.date_id
    JOIN dim_time t ON f.pu_time_id = t.time_id
    WHERE d.is_weekend = 0
      AND f.trip_distance > 0
      AND f.trip_duration_seconds > 0
    GROUP BY f.pu_location_id, distance_tier
)
SELECT
    COALESCE(l.borough, 'ALL BOROUGHS') AS borough,
    CASE g.distance_tier
        WHEN 1 THEN '1. Short (< 2 mi)'
        WHEN 2 THEN '2. Medium (2 - 4.99 mi)'
        WHEN 3 THEN '3. Long (5 - 9.99 mi)'
        WHEN 4 THEN '4. Very Long (10+ mi)'
    END AS distance_bucket,
    ROUND(SUM(g.rush_duration_sum) / NULLIF(SUM(g.rush_duration_count), 0), 2) AS rush_hour_duration_min,
    ROUND(SUM(g.off_peak_duration_sum) / NULLIF(SUM(g.off_peak_duration_count), 0), 2) AS off_peak_duration_min,
    ROUND(SUM(g.rush_speed_sum) / NULLIF(SUM(g.rush_speed_count), 0), 2) AS rush_hour_speed_mph,
    ROUND(SUM(g.off_peak_speed_sum) / NULLIF(SUM(g.off_peak_speed_count), 0), 2) AS off_peak_speed_mph
FROM trip_groups g
JOIN dim_location l ON g.pu_location_id = l.location_id
GROUP BY l.borough, g.distance_tier WITH ROLLUP;

-- Q3b - Covering distance-range index optimization, analytical SQL unchanged
-- Trip time efficiency for mid-range trips (2-5 mi)
SELECT 
    l.borough,
    l.zone,
    t.time_period,
    t.hour,
    COUNT(f.trip_id) AS trip_count,
    ROUND(AVG(f.trip_distance), 2) AS avg_distance_miles,
    ROUND(AVG(f.trip_duration_seconds) / 60.0, 2) AS avg_duration_minutes,
    ROUND(AVG(f.estimated_speed_mph), 2) AS avg_speed_mph
FROM fact_trip_records f
JOIN dim_location l ON f.pu_location_id = l.location_id
JOIN dim_date d     ON f.pu_date_id = d.date_id
JOIN dim_time t     ON f.pu_time_id = t.time_id
WHERE d.is_weekend = 0
  AND f.trip_distance BETWEEN 2.00 AND 5.00
  AND f.trip_duration_seconds > 0
GROUP BY 
    l.borough, 
    l.zone, 
    t.time_period, 
    t.hour
ORDER BY 
    l.borough, 
    l.zone, 
    t.hour;
