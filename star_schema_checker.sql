USE source_db;

-- =====================================================================
-- 1. TABLE ROW COUNTS RECONCILIATION
-- Checks whether all dimensions are seeded and facts match the raw source
-- =====================================================================
SELECT 'Raw Source (yellow_taxi_trips)' AS table_name, COUNT(*) AS row_count FROM yellow_taxi_trips
UNION ALL
SELECT 'Valid Raw Trips (Non-null Datetimes)', COUNT(*) FROM yellow_taxi_trips WHERE tpep_pickup_datetime IS NOT NULL AND tpep_dropoff_datetime IS NOT NULL
UNION ALL
SELECT 'Fact Table (fact_trip_records)', COUNT(*) FROM fact_trip_records
UNION ALL
SELECT 'Dimension: Date (dim_date)', COUNT(*) FROM dim_date
UNION ALL
SELECT 'Dimension: Time (dim_time)', COUNT(*) FROM dim_time
UNION ALL
SELECT 'Dimension: Location (dim_location)', COUNT(*) FROM dim_location
UNION ALL
SELECT 'Dimension: Payment (dim_payment)', COUNT(*) FROM dim_payment
UNION ALL
SELECT 'Dimension: Rate Code (dim_rate_code)', COUNT(*) FROM dim_rate_code;


-- =====================================================================
-- 2. METRIC TOTALS RECONCILIATION
-- Ensures no monetary or distance data was lost, corrupted, or altered
-- =====================================================================
SELECT 
    'Raw Source' AS dataset,
    COUNT(*) AS total_trips,
    ROUND(SUM(trip_distance), 2) AS total_distance,
    ROUND(SUM(fare_amount), 2) AS total_fare,
    ROUND(SUM(tip_amount), 2) AS total_tips,
    ROUND(SUM(total_amount), 2) AS total_amount
FROM yellow_taxi_trips
WHERE tpep_pickup_datetime IS NOT NULL 
  AND tpep_dropoff_datetime IS NOT NULL

UNION ALL

SELECT 
    'Star Schema Fact' AS dataset,
    COUNT(*) AS total_trips,
    ROUND(SUM(trip_distance), 2) AS total_distance,
    ROUND(SUM(fare_amount), 2) AS total_fare,
    ROUND(SUM(tip_amount), 2) AS total_tips,
    ROUND(SUM(total_amount), 2) AS total_amount
FROM fact_trip_records;


-- =====================================================================
-- 3. REFERENTIAL INTEGRITY & ORPHAN CHECKS
-- Because FOREIGN_KEY_CHECKS were disabled during bulk loading,
-- ensure zero orphan foreign keys exist (all counts should be 0)
-- =====================================================================
SELECT 
    -- Date checks
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_date d ON f.pu_date_id = d.date_id WHERE d.date_id IS NULL) AS orphan_pu_date_count,
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_date d ON f.do_date_id = d.date_id WHERE d.date_id IS NULL) AS orphan_do_date_count,
    
    -- Time checks
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_time t ON f.pu_time_id = t.time_id WHERE t.time_id IS NULL) AS orphan_pu_time_count,
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_time t ON f.do_time_id = t.time_id WHERE t.time_id IS NULL) AS orphan_do_time_count,
    
    -- Location checks
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_location l ON f.pu_location_id = l.location_id WHERE l.location_id IS NULL) AS orphan_pu_location_count,
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_location l ON f.do_location_id = l.location_id WHERE l.location_id IS NULL) AS orphan_do_location_count,
    
    -- Payment & Rate code checks
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_payment p ON f.payment_id = p.payment_id WHERE p.payment_id IS NULL) AS orphan_payment_count,
    (SELECT COUNT(*) FROM fact_trip_records f LEFT JOIN dim_rate_code r ON f.rate_code_id = r.rate_code_id WHERE r.rate_code_id IS NULL) AS orphan_rate_code_count;


-- =====================================================================
-- 4. DERIVED MEASURES & DATA QUALITY SANITY CHECK
-- Checks that calculated measures (duration and speed) are populated
-- =====================================================================
SELECT 
    COUNT(*) AS total_rows,
    MIN(trip_duration_seconds) AS min_duration_sec,
    ROUND(AVG(trip_duration_seconds), 1) AS avg_duration_sec,
    MAX(trip_duration_seconds) AS max_duration_sec,
    MIN(estimated_speed_mph) AS min_speed_mph,
    ROUND(AVG(estimated_speed_mph), 2) AS avg_speed_mph,
    MAX(estimated_speed_mph) AS max_speed_mph,
    SUM(CASE WHEN trip_duration_seconds < 0 THEN 1 ELSE 0 END) AS negative_duration_count,
    SUM(CASE WHEN estimated_speed_mph > 100 THEN 1 ELSE 0 END) AS extreme_speed_count
FROM fact_trip_records;


-- =====================================================================
-- 5. FULL 5-WAY STAR SCHEMA JOIN PREVIEW
-- Validates that the facts connect seamlessly across all 5 dimensions
-- =====================================================================
SELECT 
    f.trip_id,
    pu_d.date AS pickup_date,
    pu_d.day_of_week,
    pu_t.time_period AS pickup_period,
    pu_l.borough AS pickup_borough,
    pu_l.zone AS pickup_zone,
    do_l.borough AS dropoff_borough,
    do_l.zone AS dropoff_zone,
    p.payment_method,
    r.rate_description,
    f.trip_distance,
    f.trip_duration_seconds,
    f.estimated_speed_mph,
    f.total_amount
FROM fact_trip_records f
JOIN dim_date pu_d       ON f.pu_date_id = pu_d.date_id
JOIN dim_time pu_t       ON f.pu_time_id = pu_t.time_id
JOIN dim_location pu_l   ON f.pu_location_id = pu_l.location_id
JOIN dim_location do_l   ON f.do_location_id = do_l.location_id
JOIN dim_payment p       ON f.payment_id = p.payment_id
JOIN dim_rate_code r     ON f.rate_code_id = r.rate_code_id
LIMIT 10;
