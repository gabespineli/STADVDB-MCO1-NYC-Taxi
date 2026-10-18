-- Read-only, full-population warehouse acceptance checks.
-- Run AFTER load_fact.sql finishes, with no raw/fact writers running.
-- These scans can take time; they are not dashboard connectivity probes.
-- Inspect every result and any warnings; this file does not auto-certify a load.
USE source_db;

-- 1. Counts: facts must match the accepted ETL view, not all 12 raw files.
SELECT 'Raw source' AS table_name, COUNT(*) AS row_count FROM yellow_taxi_trips
UNION ALL SELECT 'Eligible 2025 source', COUNT(*) FROM etl_trip_source_2025
UNION ALL SELECT 'Warehouse facts', COUNT(*) FROM fact_trip_records
UNION ALL SELECT 'Date (expected 366 on a fresh seed)', COUNT(*) FROM dim_date
UNION ALL SELECT 'Time (expected 1440)', COUNT(*) FROM dim_time
UNION ALL SELECT 'Location (expected 266 including unknown)', COUNT(*) FROM dim_location
UNION ALL SELECT 'Payment (expected 7)', COUNT(*) FROM dim_payment
UNION ALL SELECT 'Rate code (expected 7)', COUNT(*) FROM dim_rate_code;

-- 2. Same eligibility AND same DECIMAL conversions on both sides.
-- Compare every sum and NULL count. Matching sums alone cannot prove NULL fidelity.
SELECT
    'Accepted transformed source' AS dataset,
    COUNT(*) AS total_trips,
    SUM(trip_distance) AS trip_distance_sum,
    SUM(fare_amount) AS fare_amount_sum,
    SUM(extra) AS extra_sum,
    SUM(mta_tax) AS mta_tax_sum,
    SUM(tip_amount) AS tip_amount_sum,
    SUM(tolls_amount) AS tolls_amount_sum,
    SUM(improvement_surcharge) AS improvement_surcharge_sum,
    SUM(total_amount) AS total_amount_sum,
    SUM(airport_fee) AS airport_fee_sum,
    SUM(cbd_congestion_fee) AS cbd_congestion_fee_sum,
    SUM(trip_duration_seconds) AS trip_duration_seconds_sum,
    SUM(estimated_speed_mph) AS estimated_speed_mph_sum,
    SUM(trip_distance IS NULL) AS trip_distance_nulls,
    SUM(fare_amount IS NULL) AS fare_amount_nulls,
    SUM(extra IS NULL) AS extra_nulls,
    SUM(mta_tax IS NULL) AS mta_tax_nulls,
    SUM(tip_amount IS NULL) AS tip_amount_nulls,
    SUM(tolls_amount IS NULL) AS tolls_amount_nulls,
    SUM(improvement_surcharge IS NULL) AS improvement_surcharge_nulls,
    SUM(total_amount IS NULL) AS total_amount_nulls,
    SUM(airport_fee IS NULL) AS airport_fee_nulls,
    SUM(cbd_congestion_fee IS NULL) AS cbd_congestion_fee_nulls,
    SUM(trip_duration_seconds IS NULL) AS trip_duration_seconds_nulls,
    SUM(estimated_speed_mph IS NULL) AS estimated_speed_mph_nulls
FROM etl_trip_source_2025
UNION ALL
SELECT
    'Warehouse facts' AS dataset,
    COUNT(*) AS total_trips,
    SUM(trip_distance) AS trip_distance_sum,
    SUM(fare_amount) AS fare_amount_sum,
    SUM(extra) AS extra_sum,
    SUM(mta_tax) AS mta_tax_sum,
    SUM(tip_amount) AS tip_amount_sum,
    SUM(tolls_amount) AS tolls_amount_sum,
    SUM(improvement_surcharge) AS improvement_surcharge_sum,
    SUM(total_amount) AS total_amount_sum,
    SUM(airport_fee) AS airport_fee_sum,
    SUM(cbd_congestion_fee) AS cbd_congestion_fee_sum,
    SUM(trip_duration_seconds) AS trip_duration_seconds_sum,
    SUM(estimated_speed_mph) AS estimated_speed_mph_sum,
    SUM(trip_distance IS NULL) AS trip_distance_nulls,
    SUM(fare_amount IS NULL) AS fare_amount_nulls,
    SUM(extra IS NULL) AS extra_nulls,
    SUM(mta_tax IS NULL) AS mta_tax_nulls,
    SUM(tip_amount IS NULL) AS tip_amount_nulls,
    SUM(tolls_amount IS NULL) AS tolls_amount_nulls,
    SUM(improvement_surcharge IS NULL) AS improvement_surcharge_nulls,
    SUM(total_amount IS NULL) AS total_amount_nulls,
    SUM(airport_fee IS NULL) AS airport_fee_nulls,
    SUM(cbd_congestion_fee IS NULL) AS cbd_congestion_fee_nulls,
    SUM(trip_duration_seconds IS NULL) AS trip_duration_seconds_nulls,
    SUM(estimated_speed_mph IS NULL) AS estimated_speed_mph_nulls
FROM fact_trip_records;

-- 3. All eight orphan counts must be zero. FK checks also stay ON during ETL.
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

-- 4. Range and quality checks. Extreme speeds are flags to investigate, not
-- an automatic exclusion rule; NULL speed is deliberately not treated as zero.
SELECT COUNT(*) AS total_rows,
    MIN(trip_duration_seconds) AS min_duration_seconds,
    MAX(trip_duration_seconds) AS max_duration_seconds,
    SUM(trip_duration_seconds IS NULL OR trip_duration_seconds NOT BETWEEN 1 AND 86400) AS invalid_duration_count,
    SUM(pu_date_id < 20250101 OR pu_date_id >= 20260101) AS pickup_outside_2025_count,
    SUM(do_date_id < 20250101 OR do_date_id > 20260101) AS dropoff_outside_calendar_count,
    SUM(trip_distance < 0) AS negative_distance_count,
    SUM(estimated_speed_mph < 0) AS negative_speed_count,
    SUM(estimated_speed_mph > 100) AS extreme_speed_count,
    SUM(estimated_speed_mph IS NULL) AS unavailable_speed_count
FROM fact_trip_records;

-- 5. Verify hour labels directly; Late Night wraps midnight, so a single
-- MIN(hour)/MAX(hour) per period would misleadingly suggest one continuous span.
SELECT `hour`, time_period, COUNT(*) AS minute_rows
FROM dim_time GROUP BY `hour`, time_period ORDER BY `hour`;
SELECT location_id, zone, borough FROM dim_location
WHERE zone IS NULL OR borough IS NULL OR zone LIKE 'Zone %' OR zone = 'nan' OR borough = 'nan';
SELECT payment_id, payment_method FROM dim_payment ORDER BY payment_id;
SELECT rate_code_id, rate_description FROM dim_rate_code ORDER BY rate_code_id;

-- 6. Preview all eight relationships, including drop-off date and time.
SELECT f.trip_id, pu_d.date AS pickup_date, do_d.date AS dropoff_date,
    pu_d.day_of_week, pu_t.time_period AS pickup_period, do_t.time_period AS dropoff_period,
    pu_l.borough AS pickup_borough, pu_l.zone AS pickup_zone,
    do_l.borough AS dropoff_borough, do_l.zone AS dropoff_zone,
    p.payment_method, r.rate_description, f.trip_distance,
    f.trip_duration_seconds, f.estimated_speed_mph, f.total_amount
FROM fact_trip_records f
JOIN dim_date pu_d ON f.pu_date_id = pu_d.date_id
JOIN dim_date do_d ON f.do_date_id = do_d.date_id
JOIN dim_time pu_t ON f.pu_time_id = pu_t.time_id
JOIN dim_time do_t ON f.do_time_id = do_t.time_id
JOIN dim_location pu_l ON f.pu_location_id = pu_l.location_id
JOIN dim_location do_l ON f.do_location_id = do_l.location_id
JOIN dim_payment p ON f.payment_id = p.payment_id
JOIN dim_rate_code r ON f.rate_code_id = r.rate_code_id
LIMIT 10;
