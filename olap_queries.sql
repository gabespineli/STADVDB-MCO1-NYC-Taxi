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

-- Hourly trip demand comparison (weekday vs weekend)
SELECT 
    l.borough,
    t.time_period,
    t.hour,
    SUM(CASE WHEN d.is_weekend = 0 THEN 1 ELSE 0 END) AS weekday_pickups,
    SUM(CASE WHEN d.is_weekend = 1 THEN 1 ELSE 0 END) AS weekend_pickups,
    ROUND(SUM(CASE WHEN d.is_weekend = 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT CASE WHEN d.is_weekend = 0 THEN d.date END), 0), 2) AS avg_weekday_hourly_pickups,
    ROUND(SUM(CASE WHEN d.is_weekend = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT CASE WHEN d.is_weekend = 1 THEN d.date END), 0), 2) AS avg_weekend_hourly_pickups
FROM fact_trip_records f
JOIN dim_location l ON f.pu_location_id = l.location_id
JOIN dim_date d     ON f.pu_date_id = d.date_id
JOIN dim_time t     ON f.pu_time_id = t.time_id
GROUP BY
    l.borough, 
    t.time_period, 
    t.hour
ORDER BY 
    l.borough, 
    t.hour;

-- Late-night trip demand consistency (date hierarchy aggregation)
SELECT 
    COALESCE(l.zone, 'ALL ZONES') AS zone,
    COALESCE(CAST(d.year AS CHAR), 'All Years') AS yr,
    COALESCE(CAST(d.quarter AS CHAR), 'Year Subtotal') AS qtr,
    COALESCE(CAST(d.month AS CHAR), 'Quarter Subtotal') AS mo,
    COUNT(f.trip_id) AS late_night_pickups
FROM fact_trip_records f
JOIN dim_location l ON f.pu_location_id = l.location_id
JOIN dim_date d     ON f.pu_date_id = d.date_id
JOIN dim_time t     ON f.pu_time_id = t.time_id
WHERE t.time_period = 'Late Night'
GROUP BY 
    l.zone, 
    d.year, 
    d.quarter, 
    d.month WITH ROLLUP;

-- Q2
-- Payment methods across fare ranges
SELECT 
    COALESCE(
        CASE 
            WHEN f.fare_amount < 10 THEN '1. Under $10'
            WHEN f.fare_amount BETWEEN 10 AND 24.99 THEN '2. $10 - $24.99'
            WHEN f.fare_amount BETWEEN 25 AND 49.99 THEN '3. $25 - $49.99'
            ELSE '4. $50 and Above'
        END, 
        'ALL FARE TIERS'
    ) AS fare_range,
    SUM(CASE WHEN p.payment_method = 'Credit Card' THEN 1 ELSE 0 END) AS credit_card_trips,
    SUM(CASE WHEN p.payment_method = 'Cash' THEN 1 ELSE 0 END) AS cash_trips,
    SUM(CASE WHEN p.payment_method NOT IN ('Credit Card', 'Cash') THEN 1 ELSE 0 END) AS other_payment_trips,
    COUNT(f.trip_id) AS total_trips,
    ROUND(AVG(f.tip_amount), 2) AS avg_tip_amount
FROM fact_trip_records f
JOIN dim_payment p ON f.payment_id = p.payment_id
WHERE f.fare_amount > 0
GROUP BY 
    CASE 
        WHEN f.fare_amount < 10 THEN '1. Under $10'
        WHEN f.fare_amount BETWEEN 10 AND 24.99 THEN '2. $10 - $24.99'
        WHEN f.fare_amount BETWEEN 25 AND 49.99 THEN '3. $25 - $49.99'
        ELSE '4. $50 and Above'
    END WITH ROLLUP;

-- Payment methods by borough and time period
SELECT 
    COALESCE(l.borough, 'ALL BOROUGHS') AS borough,
    COALESCE(t.time_period, 'All Time Periods') AS time_period,
    COALESCE(p.payment_method, 'All Payment Methods') AS payment_method,
    COUNT(f.trip_id) AS trip_count,
    ROUND(AVG(f.fare_amount), 2) AS avg_fare,
    ROUND(AVG(f.tip_amount), 2) AS avg_tip,
    ROUND(AVG(f.total_amount), 2) AS avg_total
FROM fact_trip_records f
JOIN dim_location l ON f.pu_location_id = l.location_id
JOIN dim_time t     ON f.pu_time_id = t.time_id
JOIN dim_payment p  ON f.payment_id = p.payment_id
WHERE f.fare_amount > 0
GROUP BY 
    l.borough, 
    t.time_period, 
    p.payment_method WITH ROLLUP;

-- Q3
-- Rush hour vs off-peak trip time efficiency
SELECT 
    COALESCE(l.borough, 'ALL BOROUGHS') AS borough,
    COALESCE(
        CASE 
            WHEN f.trip_distance < 2 THEN '1. Short (< 2 mi)'
            WHEN f.trip_distance BETWEEN 2 AND 4.99 THEN '2. Medium (2 - 4.99 mi)'
            WHEN f.trip_distance BETWEEN 5 AND 9.99 THEN '3. Long (5 - 9.99 mi)'
            ELSE '4. Very Long (10+ mi)'
        END,
        'All Distance Tiers'
    ) AS distance_bucket,
    ROUND(AVG(CASE WHEN t.time_period IN ('Morning Rush', 'Evening Rush', 'Rush Hour') THEN f.trip_duration_seconds / 60.0 END), 2) AS rush_hour_duration_min,
    ROUND(AVG(CASE WHEN t.time_period NOT IN ('Morning Rush', 'Evening Rush', 'Rush Hour') THEN f.trip_duration_seconds / 60.0 END), 2) AS off_peak_duration_min,
    ROUND(AVG(CASE WHEN t.time_period IN ('Morning Rush', 'Evening Rush', 'Rush Hour') THEN f.estimated_speed_mph END), 2) AS rush_hour_speed_mph,
    ROUND(AVG(CASE WHEN t.time_period NOT IN ('Morning Rush', 'Evening Rush', 'Rush Hour') THEN f.estimated_speed_mph END), 2) AS off_peak_speed_mph
FROM fact_trip_records f
JOIN dim_location l ON f.pu_location_id = l.location_id
JOIN dim_date d     ON f.pu_date_id = d.date_id
JOIN dim_time t     ON f.pu_time_id = t.time_id
WHERE d.is_weekend = 0
  AND f.trip_distance > 0
  AND f.trip_duration_seconds > 0
GROUP BY 
    l.borough,
    CASE 
        WHEN f.trip_distance < 2 THEN '1. Short (< 2 mi)'
        WHEN f.trip_distance BETWEEN 2 AND 4.99 THEN '2. Medium (2 - 4.99 mi)'
        WHEN f.trip_distance BETWEEN 5 AND 9.99 THEN '3. Long (5 - 9.99 mi)'
        ELSE '4. Very Long (10+ mi)'
    END WITH ROLLUP;

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
